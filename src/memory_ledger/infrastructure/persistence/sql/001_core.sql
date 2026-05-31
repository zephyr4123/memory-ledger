-- ═══════════════════════════════════════════════════════════════════════
-- memory-ledger · 001_core.sql — 账本核心表 + 通用触发器 (entity-agnostic)
-- ═══════════════════════════════════════════════════════════════════════
--
-- 这一份是"基本不用动"的核心层. 你的业务实体表 + effective_<entity>_at
-- 函数在 002_example_todo.sql / 你自己的迁移里写.
--
-- 与早期模板 (docs/02-schema-template.sql) 相比, 本文件修复了一批已确认缺陷:
--   * status 与 applied_at / rejected_at / superseded_by / expired_at 的耦合
--     用 CHECK 约束钉死 (早期版本靠约定, reject 端点漏写时间戳会静默生效)
--   * 新增 expired_at 时间戳列, EXPIRED 真正落地 (早期 EXPIRED 是 no-op)
--   * CASE 表达式补 ELSE, 未知 kind / 未映射 source_layer 不再静默放行/抢 winner
--   * 幂等唯一索引: 同一 source 不重复写同一 (entity,row,field,kind) intent
--   * 一个 (user,entity,row,field) 至多一条 live PATCH 的硬约束 (并发安全)
--   * auto-supersede 触发器: 新 APPLIED PATCH 落地自动 supersede 旧 live PATCH
--   * advisory-lock 序列化同 key 写入 (见 runtime, 防并发双 live)
--
-- 测试环境: PostgreSQL 14+. 需要 jsonb / GENERATED column / partial index.

-- ───────────────────────────────────────────────────────────────────────
-- 公用 helper · updated_at 自动维护
-- ───────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION ml_set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = clock_timestamp();
    RETURN NEW;
END;
$$;


-- ═══════════════════════════════════════════════════════════════════════
-- l15_change_intents — 账本核心表
-- ═══════════════════════════════════════════════════════════════════════
--
-- 唯一需要随业务改的是 target_entity 的 CHECK 列表. 见下方 -- TODO.
-- 加新 entity: 改这里 + 写对应 effective_<entity>_at 函数 (002 模板).

CREATE TABLE l15_change_intents (
    id                 BIGSERIAL PRIMARY KEY,

    -- 你的 user 主键 (TEXT 以兼容 uuid / 外部 id). 如需外键自行加 REFERENCES.
    user_id            TEXT NOT NULL,

    -- 4-kind (通用, 不改)
    kind               TEXT NOT NULL
                       CHECK (kind IN ('PATCH','ASSERT','ANNOTATE','FLAG')),

    -- TODO: 列出所有可被 intent 锚定的业务实体表名.
    -- 加新 entity 必须改这里 + 写对应 effective_<entity>_at 函数.
    target_entity      TEXT NOT NULL
                       CHECK (target_entity IN (
                           'todo_item',
                           'project'
                       )),

    -- target 锚点 (通用)
    target_date        DATE,            -- entity 若按日期分区填这个, 否则留空
    target_row_id      TEXT,            -- entity 行主键 (转 TEXT)
    target_field       TEXT,            -- PATCH/FLAG 必填, ANNOTATE 可空

    -- 载荷 (通用)
    patch_json         JSONB NOT NULL,
    reason             TEXT NOT NULL DEFAULT '',

    -- ─── Source Provenance ────────────────────────────────────────
    source_layer       TEXT NOT NULL
                       CHECK (source_layer IN (
                           'USER_DIRECT','L2_FORM','L2_CHAT',
                           'L2_VOICE','AGENT_INFERENCE'
                       )),
    -- generated column: 让 priority 进索引 (查 PATCH winner 用).
    -- ELSE 99: 未映射的 layer 不再得到 NULL (NULLS FIRST 会抢 winner), 而是垫底.
    source_priority    SMALLINT GENERATED ALWAYS AS (
        CASE source_layer
            WHEN 'USER_DIRECT'     THEN 0
            WHEN 'L2_FORM'         THEN 1
            WHEN 'L2_CHAT'         THEN 2
            WHEN 'L2_VOICE'        THEN 3
            WHEN 'AGENT_INFERENCE' THEN 4
            ELSE 99
        END
    ) STORED,
    source_table       TEXT NOT NULL,   -- 原话所在表 (e.g. 'chat_message')
    source_id          TEXT NOT NULL,   -- 原话所在行主键
    source_quote       TEXT,            -- 原话截取 (debugging 黄金字段)
    extracted_by       TEXT,            -- LLM model id / pipeline name (可选)
    confidence         NUMERIC(3, 2) NOT NULL DEFAULT 1.0
                       CHECK (confidence >= 0 AND confidence <= 1),

    -- ─── State Machine ────────────────────────────────────────────
    status             TEXT NOT NULL DEFAULT 'PROPOSED'
                       CHECK (status IN (
                           'PROPOSED','APPLIED','SUPERSEDED','REJECTED','EXPIRED'
                       )),
    applied_at         TIMESTAMPTZ,
    -- DEFERRABLE INITIALLY DEFERRED: auto-supersede 触发器在 BEFORE INSERT 阶段把
    -- 旧行 superseded_by 指向新行的 id, 而新行此刻尚未真正插入. 延迟到 commit 校验
    -- FK, 使 "先标旧行 superseded → 再插新行" 这个顺序合法 (新行届时已存在).
    superseded_by      BIGINT REFERENCES l15_change_intents(id) ON DELETE SET NULL
                       DEFERRABLE INITIALLY DEFERRED,
    rejected_reason    TEXT,
    rejected_at        TIMESTAMPTZ,
    expired_at         TIMESTAMPTZ,     -- EXPIRED 用, 与 rejected_at 同样按 as_of 比较

    created_at         TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),

    -- ─── Shape 强制: 每 kind 一份 patch_json 形状校验 ──────────────
    -- ELSE false: 未知 kind 直接拒, 不再因 CASE 无匹配返回 NULL 而放行.
    CONSTRAINT chk_patch_kind_shape CHECK (
        CASE kind
            WHEN 'PATCH' THEN
                target_field IS NOT NULL
                AND jsonb_typeof(patch_json) = 'object'
                AND patch_json ? target_field
            WHEN 'ASSERT' THEN
                jsonb_typeof(patch_json) = 'object'
                AND patch_json != '{}'::jsonb
            WHEN 'ANNOTATE' THEN
                jsonb_typeof(patch_json) = 'object'
                AND patch_json ? 'annotation'
                AND jsonb_typeof(patch_json -> 'annotation') = 'string'
            WHEN 'FLAG' THEN
                target_field IS NOT NULL
                AND jsonb_typeof(patch_json) = 'object'
                AND patch_json ? 'flag_reason'
            ELSE false
        END
    ),

    -- ─── 状态 ↔ 时间戳列 耦合 (核心修复) ──────────────────────────
    -- effective view 靠时间戳列做时光机过滤, 这些 CHECK 保证状态翻转时
    -- 对应时间戳不会为空 — 杜绝 "REJECTED 但 rejected_at NULL → 仍生效".
    CONSTRAINT chk_applied_has_ts CHECK (
        status <> 'APPLIED' OR applied_at IS NOT NULL
    ),
    CONSTRAINT chk_superseded_has_ref CHECK (
        status <> 'SUPERSEDED' OR superseded_by IS NOT NULL
    ),
    CONSTRAINT chk_rejected_has_ts CHECK (
        status <> 'REJECTED' OR rejected_at IS NOT NULL
    ),
    CONSTRAINT chk_expired_has_ts CHECK (
        status <> 'EXPIRED' OR expired_at IS NOT NULL
    ),
    -- 被 supersede 的行同样应保留其原 applied_at (它曾经 APPLIED 过)
    CONSTRAINT chk_superseded_was_applied CHECK (
        status <> 'SUPERSEDED' OR applied_at IS NOT NULL
    )
);

-- ─── 索引 ─────────────────────────────────────────────────────────

-- 核心: PATCH winner 查找走这条 partial index
CREATE INDEX idx_l15_active_priority ON l15_change_intents (
    user_id, target_entity, target_date, target_field,
    source_priority ASC, confidence DESC, applied_at DESC, id DESC
) WHERE status = 'APPLIED' AND superseded_by IS NULL;

-- 反查 source: "这条 chat message 产出了哪些 intent"
CREATE INDEX idx_l15_source ON l15_change_intents (source_table, source_id);

-- audit: 按用户/kind/时间逆序拉
CREATE INDEX idx_l15_kind_time ON l15_change_intents (user_id, kind, created_at DESC);

-- patch_json 内部字段查询
CREATE INDEX idx_l15_patch_json ON l15_change_intents USING GIN (patch_json);

-- 按 entity row 拉所有 intent (effective view 函数用)
CREATE INDEX idx_l15_target_row ON l15_change_intents (user_id, target_entity, target_row_id)
    WHERE target_row_id IS NOT NULL;

-- ─── 幂等 + 并发硬约束 ────────────────────────────────────────────

-- 幂等: 同一来源 (source_table, source_id) 不该对同一 (entity,row,field,kind)
-- 重复写非拒绝态的 intent. retry / 双提交 / LLM 重复 emit 时由 ON CONFLICT 兜住.
-- (target_row_id / target_field 可能为 NULL, COALESCE 成哨兵值参与唯一性.)
CREATE UNIQUE INDEX uq_l15_idempotent ON l15_change_intents (
    user_id, source_table, source_id, target_entity,
    COALESCE(target_row_id, ''), COALESCE(target_field, ''), kind
) WHERE status <> 'REJECTED';

-- 并发安全: 任一 (user, entity, row, field) 至多一条 live PATCH.
-- 配合 runtime 的 advisory lock + auto-supersede 触发器, 杜绝 "两条 live PATCH".
CREATE UNIQUE INDEX uq_l15_one_live_patch ON l15_change_intents (
    user_id, target_entity, COALESCE(target_row_id, ''), target_field
) WHERE kind = 'PATCH' AND status = 'APPLIED' AND superseded_by IS NULL;

CREATE TRIGGER trg_l15_updated_at
    BEFORE UPDATE ON l15_change_intents
    FOR EACH ROW EXECUTE FUNCTION ml_set_updated_at();


-- ═══════════════════════════════════════════════════════════════════════
-- auto-supersede 触发器 — 新 APPLIED PATCH 落地, 自动 supersede 旧 live PATCH
-- ═══════════════════════════════════════════════════════════════════════
--
-- 把 supersede 从"应用层两步手动 (insert + update)"变成数据库不变量, 对所有
-- 写入方 (含裸 SQL / 别的微服务) 生效.
--
-- 为什么是 BEFORE INSERT 而不是 AFTER:
--   uq_l15_one_live_patch 唯一索引要求任一 (user,entity,row,field) 至多一条
--   live PATCH. 若用 AFTER INSERT, 插入新行的"瞬间"旧行仍 live → 两条 live →
--   唯一索引在 AFTER 触发器还没来得及标掉旧行前就拒掉合法的连续改动.
--   改成 BEFORE INSERT: 先从序列取出 NEW.id, 把旧 live 行 superseded_by 指向
--   它并标 SUPERSEDED, 然后真正 INSERT 时旧行已不 live, 唯一索引只看到新行.
--   这样触发器 (DB 不变量) 与唯一索引 (硬兜底) 共存.
--
-- 并发: 同 key 的合法连续写由 runtime 的 pg_advisory_xact_lock 序列化, 不会撞
--   唯一索引. 若有人绕过 runtime 并发裸插同 key, 第二个会拿到唯一索引冲突
--   (安全失败), 而不是静默留下两条 live PATCH.

CREATE OR REPLACE FUNCTION l15_auto_supersede()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    -- 先确定本行 id (BEFORE INSERT 时 BIGSERIAL 默认尚未必填充)
    IF NEW.id IS NULL THEN
        NEW.id := nextval(pg_get_serial_sequence('l15_change_intents', 'id'));
    END IF;

    UPDATE l15_change_intents prev
    SET superseded_by = NEW.id,
        status        = 'SUPERSEDED'
    WHERE prev.user_id       = NEW.user_id
      AND prev.target_entity = NEW.target_entity
      AND prev.target_row_id IS NOT DISTINCT FROM NEW.target_row_id
      AND prev.target_field  = NEW.target_field
      AND prev.kind          = 'PATCH'
      AND prev.status        = 'APPLIED'
      AND prev.superseded_by IS NULL
      AND prev.id <> NEW.id;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_l15_auto_supersede
    BEFORE INSERT ON l15_change_intents
    FOR EACH ROW
    WHEN (NEW.kind = 'PATCH' AND NEW.status = 'APPLIED'
          AND NEW.superseded_by IS NULL)
    EXECUTE FUNCTION l15_auto_supersede();


-- ═══════════════════════════════════════════════════════════════════════
-- 通用 helper: 一条 intent 在某时点是否"活的" (供 effective_<entity>_at 复用)
-- ═══════════════════════════════════════════════════════════════════════
--
-- 把时光机过滤谓词收口到一个 IMMUTABLE 函数, 各 effective_<entity>_at 不再
-- 重复手写 (早期模板每个实体抄一遍 4 行谓词, 容易漂). superseder 的 applied_at
-- 由调用方用 LEFT JOIN 解出后传入, 避免 correlated 子查询 (早期性能悬崖).
--
-- 入参:
--   p_applied_at        本 intent 的 applied_at
--   p_rejected_at       本 intent 的 rejected_at
--   p_expired_at        本 intent 的 expired_at
--   p_superseder_applied_at  其 superseder 的 applied_at (无则 NULL)
--   p_as_of             查询时点
-- 返回: 截至 p_as_of, 这条 intent 是否计入 effective.

CREATE OR REPLACE FUNCTION l15_is_live_at(
    p_applied_at             TIMESTAMPTZ,
    p_rejected_at            TIMESTAMPTZ,
    p_expired_at             TIMESTAMPTZ,
    p_superseder_applied_at  TIMESTAMPTZ,
    p_as_of                  TIMESTAMPTZ
) RETURNS BOOLEAN
LANGUAGE sql IMMUTABLE AS $$
    SELECT p_applied_at IS NOT NULL
       AND p_applied_at <= p_as_of
       AND (p_rejected_at IS NULL OR p_rejected_at > p_as_of)
       AND (p_expired_at  IS NULL OR p_expired_at  > p_as_of)
       AND (p_superseder_applied_at IS NULL
            OR p_superseder_applied_at > p_as_of);
$$;
