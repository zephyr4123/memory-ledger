# Personal-CRM —— memory-ledger 参考应用

一个**可跑、确定性、离线**的示例,把 memory-ledger 的三大差异化在一段脚本化对话里演出来:

| 差异化 | 在这个 demo 里怎么体现 |
|---|---|
| **确定性 as-of 时光机** | Sarah 的 `employer`:`Acme Corp` → 确认 `Acme` → 确认 `Globex`。任意历史时点回看都得到当时的真相(用 DB 里 intent 的 `applied_at` 作锚点,零 Python 时钟)。 |
| **逐字 source_quote 溯源** | "你怎么知道她在 Acme?" —— 答案直接来自 `assertions[]` 里存的**原话**(`"she just started at Acme"`),不是再推理。 |
| **高危 PATCH 人工确认 banner** | 改 `employer`/`location` 一律落 `PROPOSED`,等用户拍板。`location → Berlin` 先挂起待确认,最后被**拒绝**,`location_eff` 仍是 `San Francisco`。 |

## 怎么跑

```bash
conda activate memory-ledger          # 或你的 venv
pip install -e '.[dev]'               # 含 psycopg + testcontainers

# A. 当测试跑 (推荐, 自动起一个一次性 Postgres 容器, 断言三大差异化真实发生)
pytest examples/personal_crm/tests/ -v

# B. 当 demo 跑 (连你自己的 Postgres, 打印对话 + banner)
export DATABASE_URL=postgresql://localhost/mydb
python -m examples.personal_crm.run_demo
```

> 全程不需要任何 API key:`MockExtractor` 是一张冻结的 turn 表,不调任何模型。
> 想接真模型?实现 `memory_ledger.ports.extractor.Extractor`(解析模型的 JSON → `Extraction`)替换 `MockExtractor` 即可,其余不动。

## 它怎么搭起来的(对应六边形分层)

```
examples/personal_crm/
├── transcript.py      冻结的对话脚本 (6 个 ScriptedTurn, 演 9 步叙事)
├── mock_extractor.py  实现 ports.Extractor: 按轮号取脚本, 纯函数 (忽略 snapshot)
├── policy.py          person 的 AutoApplyPolicy + 字段/值别名 (纯数据)
├── snapshot.py        build_person_snapshot: effective 视图 → sanitize → 定界块
└── run_demo.py        组合根: open_postgres + AgentLoop(ledger, MockExtractor)
```

可复用的部分(`Extractor` 端口、`AgentLoop` 编排器)在**库里** (`src/memory_ledger/`);
实体特定的部分(脚本、mock、person 的 snapshot 拼装)在**示例里**——这正是六边形把
"通用核心"和"业务边缘"分开的体现。`person` 实体本身由 `003`(注册表)+ `004`(person 表
+ `effective_person_at` + 注册行)两个 opt-in 迁移装上,核心 `001/002` 不动。

详见 [docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md) 的"加一个实体"配方。
