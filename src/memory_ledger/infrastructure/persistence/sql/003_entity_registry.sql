-- ═══════════════════════════════════════════════════════════════════════
-- memory-ledger · 003_entity_registry.sql — 实体注册表 (OPT-IN, 非默认)
-- ═══════════════════════════════════════════════════════════════════════
--
-- 不在 DEFAULT_MIGRATIONS 里. 默认 path (001+002) 仍用命名 CHECK 锁白名单.
-- 应用本迁移后, "加一个实体" 从「改 001 的 CHECK 白名单 + ALTER」变成「INSERT 一行」.
--
-- 它做两件事:
--   1. 建 l15_entity 目录表 (name PK, effective_fn 记录该实体的时光机函数名)
--   2. 把 l15_change_intents.target_entity 的命名 CHECK 换成指向 l15_entity 的 FK
--
-- anti-LLM-noise 不变: FK 与 CHECK 一样是「DB 强制的封闭枚举白名单」—— 未注册的
-- target_entity 写入时被 ForeignKeyViolation 拒, 等价于原来的 CheckViolation.
--
-- 新增的唯一失效模式 (注册了但没有 effective_<entity>_at 函数 → 读时 function
-- does not exist): 由约定关闭 —— 实体的 表 + 函数 + 注册行 必须在同一迁移内一起建
-- (见 004_person.sql), 且 effective_fn NOT NULL. CI 用 to_regprocedure 断言每个
-- 注册行都有活函数 (test_entity_registry.py).
--
-- 大表注意: DROP/ADD CONSTRAINT 取 ACCESS EXCLUSIVE 锁; 生产大库建议先
--   ALTER TABLE ... ADD CONSTRAINT fk_target_entity ... NOT VALID;
--   ALTER TABLE ... VALIDATE CONSTRAINT fk_target_entity;
-- 分两步避免长时间持锁. 本文件用直写 (测试/初装库为空, 无开销).

CREATE TABLE l15_entity (
    name           TEXT PRIMARY KEY,
    -- 该实体的时光机函数名, 形如 'effective_<name>_at'. NOT NULL: 注册即承诺有函数.
    effective_fn   TEXT NOT NULL,
    registered_at  TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

-- 回填默认 path 已有的两个实体
INSERT INTO l15_entity (name, effective_fn) VALUES
    ('todo_item', 'effective_todo_item_at'),
    ('project',   'effective_project_at');

-- 命名 CHECK → FK. 因为命名 (chk_target_entity, 见 001), DROP 是确定的.
ALTER TABLE l15_change_intents DROP CONSTRAINT chk_target_entity;
ALTER TABLE l15_change_intents
    ADD CONSTRAINT fk_target_entity
    FOREIGN KEY (target_entity) REFERENCES l15_entity (name);
