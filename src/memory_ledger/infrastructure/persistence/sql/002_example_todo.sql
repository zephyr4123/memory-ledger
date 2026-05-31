-- ═══════════════════════════════════════════════════════════════════════
-- memory-ledger · 002_example_todo.sql — 示例业务实体 + effective 函数
-- ═══════════════════════════════════════════════════════════════════════
--
-- 这是 TodoAgent 示例 (todo_item / project 两个实体). 用作:
--   * 单元 / 集成测试的固定 fixture
--   * 学习 effective_<entity>_at 怎么写的样板
--
-- 真实项目里你把这两张表换成自己的业务表, 并照 PART 3 的模板给每个实体
-- 写一份 effective_<entity>_at. 记得同步改 001_core.sql 的 target_entity CHECK.
--
-- 与早期模板的差异 (修复点):
--   * effective_<entity>_at 多收一个 p_user_id 参数, 函数内强制 user_id 匹配
--     (早期函数无 user_id, 仅靠业务行推导 → 跨租户越权)
--   * superseded_by 用 LEFT JOIN 一次解出 (早期每行 2 次 correlated 子查询)
--   * 复用 l15_is_live_at() 收口时光机谓词
--   * flags 聚成数组并带 ORDER BY (早期 jsonb_object_agg 同字段静默覆盖丢历史)

-- ───────────────────────────────────────────────────────────────────────
-- 业务实体表 (示例)
-- ───────────────────────────────────────────────────────────────────────

CREATE TABLE todo_item (
    id            BIGSERIAL PRIMARY KEY,
    user_id       TEXT NOT NULL,
    title         TEXT NOT NULL,
    description   TEXT,
    status        TEXT NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending', 'in_progress', 'completed', 'cancelled')),
    priority      SMALLINT NOT NULL DEFAULT 3
                  CHECK (priority BETWEEN 1 AND 5),
    project       TEXT,
    due_date      DATE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    deleted       BOOLEAN NOT NULL DEFAULT false
);
CREATE INDEX idx_todo_user ON todo_item (user_id) WHERE deleted = false;
CREATE INDEX idx_todo_due ON todo_item (user_id, due_date) WHERE deleted = false;
CREATE TRIGGER trg_todo_updated_at
    BEFORE UPDATE ON todo_item
    FOR EACH ROW EXECUTE FUNCTION ml_set_updated_at();

CREATE TABLE project (
    id            BIGSERIAL PRIMARY KEY,
    user_id       TEXT NOT NULL,
    name          TEXT NOT NULL,
    description   TEXT,
    color         TEXT,
    archived      BOOLEAN NOT NULL DEFAULT false,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX idx_project_user ON project (user_id) WHERE archived = false;
CREATE TRIGGER trg_project_updated_at
    BEFORE UPDATE ON project
    FOR EACH ROW EXECUTE FUNCTION ml_set_updated_at();


-- ═══════════════════════════════════════════════════════════════════════
-- effective_todo_item_at — 时光机核心 (修正版模板)
-- ═══════════════════════════════════════════════════════════════════════
--
-- 改成你自己实体时:
--   1. 改 RETURNS TABLE 列 (每个 patchable 字段一对 _eff / _raw)
--   2. 改 effective_intents 的 target_entity 值 + 业务表 JOIN
--   3. 改最后 SELECT 的 COALESCE 跟 _eff 列对齐
--   4. 保留 p_user_id 参数和 l15_is_live_at 调用不动

CREATE OR REPLACE FUNCTION effective_todo_item_at(
    p_user_id   TEXT,
    p_todo_id   BIGINT,
    p_as_of_ts  TIMESTAMPTZ
)
RETURNS TABLE (
    id            BIGINT,
    user_id       TEXT,
    title         TEXT,
    description   TEXT,
    -- _effective 合并 PATCH 后 (LLM / 应用层应看到的值)
    status_eff    TEXT,
    priority_eff  SMALLINT,
    project_eff   TEXT,
    due_date_eff  DATE,
    -- _raw 原始值 (debugging / "agent 改了多少" 用)
    status_raw    TEXT,
    priority_raw  SMALLINT,
    project_raw   TEXT,
    due_date_raw  DATE,
    -- 4-kind 聚合产物
    assertions    JSONB,
    annotations   JSONB,
    flags         JSONB,
    -- audit: 本次合并用到哪些 intent
    intents_applied_as_of BIGINT[]
)
LANGUAGE sql STABLE
AS $$
    WITH effective_intents AS (
        SELECT i.*
        FROM l15_change_intents i
        JOIN todo_item t
          ON t.id = p_todo_id
         AND t.user_id = p_user_id            -- 多租户: 强制 user_id 匹配
        LEFT JOIN l15_change_intents s         -- 一次解出 superseder, 不用 correlated 子查询
          ON s.id = i.superseded_by
        WHERE i.user_id = p_user_id
          AND i.target_entity = 'todo_item'    -- TODO: 改你的 entity name
          AND i.target_row_id = p_todo_id::text
          AND l15_is_live_at(
                  i.applied_at, i.rejected_at, i.expired_at,
                  s.applied_at, p_as_of_ts)
    ),
    patch_latest AS (
        SELECT jsonb_object_agg(target_field, winning_value) AS patches
        FROM (
            SELECT DISTINCT ON (target_field)
                   target_field,
                   patch_json -> target_field AS winning_value
            FROM effective_intents
            WHERE kind = 'PATCH'
            ORDER BY target_field,
                     source_priority ASC,
                     confidence DESC,
                     applied_at DESC,
                     id DESC
        ) lp
    ),
    asserts AS (
        SELECT jsonb_agg(
            jsonb_build_object(
                'payload',      patch_json,
                'intent_id',    id,
                'source_id',    source_id,
                'source_quote', source_quote,
                'confidence',   confidence,
                'applied_at',   applied_at
            ) ORDER BY applied_at, id
        ) AS items
        FROM effective_intents WHERE kind = 'ASSERT'
    ),
    annotations_ AS (
        SELECT jsonb_agg(
            jsonb_build_object(
                'annotation',   patch_json -> 'annotation',
                'intent_id',    id,
                'source_id',    source_id,
                'source_quote', source_quote,
                'applied_at',   applied_at
            ) ORDER BY applied_at, id
        ) AS items
        FROM effective_intents WHERE kind = 'ANNOTATE'
    ),
    -- flags 聚成数组 (按 field 分组但保留多条), 带 ORDER BY → 不再静默覆盖丢历史
    flags_ AS (
        SELECT jsonb_agg(
            jsonb_build_object(
                'target_field', target_field,
                'flag_reason',  patch_json -> 'flag_reason',
                'intent_id',    id,
                'confidence',   confidence,
                'applied_at',   applied_at
            ) ORDER BY applied_at, id
        ) AS items
        FROM effective_intents
        WHERE kind = 'FLAG' AND target_field IS NOT NULL
    ),
    all_intents AS (
        SELECT array_agg(id ORDER BY applied_at, id) AS ids
        FROM effective_intents
    )
    SELECT
        t.id,
        t.user_id,
        t.title,
        t.description,
        -- _eff: COALESCE(patch winner, raw)
        COALESCE(p.patches ->> 'status',                t.status),
        COALESCE((p.patches ->> 'priority')::SMALLINT,  t.priority),
        COALESCE(p.patches ->> 'project',               t.project),
        COALESCE((p.patches ->> 'due_date')::DATE,      t.due_date),
        -- _raw
        t.status, t.priority, t.project, t.due_date,
        COALESCE(a.items,  '[]'::jsonb),
        COALESCE(an.items, '[]'::jsonb),
        COALESCE(f.items,  '[]'::jsonb),
        COALESCE(ai.ids,   ARRAY[]::BIGINT[])
    FROM todo_item t
    CROSS JOIN patch_latest p
    CROSS JOIN asserts a
    CROSS JOIN annotations_ an
    CROSS JOIN flags_ f
    CROSS JOIN all_intents ai
    WHERE t.id = p_todo_id
      AND t.user_id = p_user_id;
$$;


-- ─── effective_project_at — 第二个实体, 同款模板 ─────────────────────────

CREATE OR REPLACE FUNCTION effective_project_at(
    p_user_id    TEXT,
    p_project_id BIGINT,
    p_as_of_ts   TIMESTAMPTZ
)
RETURNS TABLE (
    id            BIGINT,
    user_id       TEXT,
    name_eff      TEXT,
    description_eff TEXT,
    color_eff     TEXT,
    name_raw      TEXT,
    description_raw TEXT,
    color_raw     TEXT,
    assertions    JSONB,
    annotations   JSONB,
    flags         JSONB,
    intents_applied_as_of BIGINT[]
)
LANGUAGE sql STABLE
AS $$
    WITH effective_intents AS (
        SELECT i.*
        FROM l15_change_intents i
        JOIN project pr
          ON pr.id = p_project_id
         AND pr.user_id = p_user_id
        LEFT JOIN l15_change_intents s
          ON s.id = i.superseded_by
        WHERE i.user_id = p_user_id
          AND i.target_entity = 'project'
          AND i.target_row_id = p_project_id::text
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
            'source_quote', source_quote, 'applied_at', applied_at
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
        pr.id, pr.user_id,
        COALESCE(pl.patches ->> 'name',        pr.name),
        COALESCE(pl.patches ->> 'description', pr.description),
        COALESCE(pl.patches ->> 'color',       pr.color),
        pr.name, pr.description, pr.color,
        COALESCE(a.items,  '[]'::jsonb),
        COALESCE(an.items, '[]'::jsonb),
        COALESCE(f.items,  '[]'::jsonb),
        COALESCE(ai.ids,   ARRAY[]::BIGINT[])
    FROM project pr
    CROSS JOIN patch_latest pl
    CROSS JOIN asserts a
    CROSS JOIN annotations_ an
    CROSS JOIN flags_ f
    CROSS JOIN all_intents ai
    WHERE pr.id = p_project_id
      AND pr.user_id = p_user_id;
$$;
