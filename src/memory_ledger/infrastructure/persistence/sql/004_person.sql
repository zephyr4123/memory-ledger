-- ═══════════════════════════════════════════════════════════════════════
-- memory-ledger · 004_person.sql — Personal-CRM 的 person 实体 (OPT-IN)
-- ═══════════════════════════════════════════════════════════════════════
--
-- 依赖 003 (注册表). 不在 DEFAULT_MIGRATIONS 里.
--
-- 把 person 的 表 + effective_person_at 函数 + l15_entity 注册行 放在同一文件,
-- 由 simple-query 协议作为单事务一次性应用 —— 结构上杜绝 "注册了但没函数".
--
-- person 是 Personal-CRM 参考应用的核心实体. effective_person_at 完全照
-- 002_example_todo.sql 的 5-CTE 模板 (l15_is_live_at 复用, p_user_id 强制多租户,
-- LEFT JOIN 解 superseder), 每个 patchable 字段一对 _eff / _raw.

-- ─── person 业务表 ───────────────────────────────────────────────
CREATE TABLE person (
    id            BIGSERIAL PRIMARY KEY,
    user_id       TEXT NOT NULL,                 -- CRM 拥有者 (非联系人本身), 多租户键
    full_name     TEXT NOT NULL,                 -- patchable: 显示身份
    employer      TEXT,                          -- patchable: 最易变, 演 supersede (Acme→Globex)
    role          TEXT,                          -- patchable: 职位, 与 employer 各自独立 live
    location      TEXT,                          -- patchable: 演 pending-banner (低置信迁居)
    comm_pref     TEXT                           -- patchable + enum 校验 (anti-noise on values)
                  CHECK (comm_pref IN ('email', 'phone', 'sms') OR comm_pref IS NULL),
    relationship  TEXT,                          -- patchable: 自由文本关系事实
    created_at    TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    deleted       BOOLEAN NOT NULL DEFAULT false
);
CREATE INDEX idx_person_user ON person (user_id) WHERE deleted = false;
CREATE TRIGGER trg_person_updated_at
    BEFORE UPDATE ON person
    FOR EACH ROW EXECUTE FUNCTION ml_set_updated_at();


-- ─── effective_person_at — 时光机 (002 模板, person 6 字段) ─────────
CREATE OR REPLACE FUNCTION effective_person_at(
    p_user_id   TEXT,
    p_person_id BIGINT,
    p_as_of_ts  TIMESTAMPTZ
)
RETURNS TABLE (
    id                BIGINT,
    user_id           TEXT,
    -- _effective (合并 PATCH 后, 应用/模型看到的值)
    full_name_eff     TEXT,
    employer_eff      TEXT,
    role_eff          TEXT,
    location_eff      TEXT,
    comm_pref_eff     TEXT,
    relationship_eff  TEXT,
    -- _raw (原始 seed 值)
    full_name_raw     TEXT,
    employer_raw      TEXT,
    role_raw          TEXT,
    location_raw      TEXT,
    comm_pref_raw     TEXT,
    relationship_raw  TEXT,
    -- 4-kind 聚合
    assertions        JSONB,
    annotations       JSONB,
    flags             JSONB,
    intents_applied_as_of BIGINT[]
)
LANGUAGE sql STABLE
AS $$
    WITH effective_intents AS (
        SELECT i.*
        FROM l15_change_intents i
        JOIN person pe
          ON pe.id = p_person_id
         AND pe.user_id = p_user_id            -- 多租户: 强制 user_id 匹配
        LEFT JOIN l15_change_intents s
          ON s.id = i.superseded_by
        WHERE i.user_id = p_user_id
          AND i.target_entity = 'person'
          AND i.target_row_id = p_person_id::text
          AND l15_is_live_at(
                  i.applied_at, i.rejected_at, i.expired_at,
                  s.applied_at, p_as_of_ts)
    ),
    patch_latest AS (
        SELECT jsonb_object_agg(target_field, winning_value) AS patches
        FROM (
            SELECT DISTINCT ON (target_field)
                   target_field, patch_json -> target_field AS winning_value
            FROM effective_intents WHERE kind = 'PATCH'
            ORDER BY target_field, source_priority ASC, confidence DESC,
                     applied_at DESC, id DESC
        ) lp
    ),
    asserts AS (
        SELECT jsonb_agg(jsonb_build_object(
            'payload', patch_json, 'intent_id', id,
            'source_id', source_id, 'source_quote', source_quote,
            'confidence', confidence, 'applied_at', applied_at
        ) ORDER BY applied_at, id) AS items
        FROM effective_intents WHERE kind = 'ASSERT'
    ),
    annotations_ AS (
        SELECT jsonb_agg(jsonb_build_object(
            'annotation', patch_json -> 'annotation', 'intent_id', id,
            'source_id', source_id, 'source_quote', source_quote,
            'applied_at', applied_at
        ) ORDER BY applied_at, id) AS items
        FROM effective_intents WHERE kind = 'ANNOTATE'
    ),
    flags_ AS (
        SELECT jsonb_agg(jsonb_build_object(
            'target_field', target_field, 'flag_reason', patch_json -> 'flag_reason',
            'intent_id', id, 'confidence', confidence, 'applied_at', applied_at
        ) ORDER BY applied_at, id) AS items
        FROM effective_intents WHERE kind = 'FLAG' AND target_field IS NOT NULL
    ),
    all_intents AS (
        SELECT array_agg(id ORDER BY applied_at, id) AS ids FROM effective_intents
    )
    SELECT
        pe.id, pe.user_id,
        COALESCE(pl.patches ->> 'full_name',    pe.full_name),
        COALESCE(pl.patches ->> 'employer',     pe.employer),
        COALESCE(pl.patches ->> 'role',         pe.role),
        COALESCE(pl.patches ->> 'location',     pe.location),
        COALESCE(pl.patches ->> 'comm_pref',    pe.comm_pref),
        COALESCE(pl.patches ->> 'relationship', pe.relationship),
        pe.full_name, pe.employer, pe.role, pe.location, pe.comm_pref, pe.relationship,
        COALESCE(a.items,  '[]'::jsonb),
        COALESCE(an.items, '[]'::jsonb),
        COALESCE(f.items,  '[]'::jsonb),
        COALESCE(ai.ids,   ARRAY[]::BIGINT[])
    FROM person pe
    CROSS JOIN patch_latest pl
    CROSS JOIN asserts a
    CROSS JOIN annotations_ an
    CROSS JOIN flags_ f
    CROSS JOIN all_intents ai
    WHERE pe.id = p_person_id
      AND pe.user_id = p_user_id;
$$;


-- ─── 注册 person (与表/函数同事务, 杜绝 "注册了但没函数") ─────────────
INSERT INTO l15_entity (name, effective_fn) VALUES ('person', 'effective_person_at');
