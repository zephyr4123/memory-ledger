# L1.5 Intent Ledger — 给 LLM Agent 的 Structured Memory

> 不是 RAG, 不是 vector. 是一份"按状态机记账、可时间旅行、有溯源"的 agent memory 设计文档 + 模板代码.

## 这是什么

一句话: **把 agent 跟用户的每一次"事实陈述 / 字段改动 / 注释 / 标疑" 记成一条 intent, 写进同一张账本表 (`l15_change_intents`), 然后通过 PG view 函数 (`effective_*_at(as_of_ts)`) 按时间戳合成"截至此刻的真相", 给 agent 下一轮当 context.**

跨会话记忆就这样实现 — 不靠 embedding, 不靠相似度.

文档全程用一个虚构的 **TodoAgent** (帮用户管理待办清单的 LLM agent) 当例子贯穿. 你 copy 走改 schema 适配自己业务即可.

## 为什么不写 RAG / vector

跟主流 memory framework (mem0 / Letta / Zep) 对比:

| 维度 | Vector Memory | Intent Ledger (本设计) |
|---|---|---|
| 召回方式 | 语义近似搜索 (embedding distance) | SQL 精确查询 (按 entity / date / field) |
| 数据形态 | 任意自然语言 chunk | 结构化 intent 行 (4-kind shape 强制) |
| 可调试 | 难追 (embedding 不可读) | 每条 intent 含 `source_quote` + `source_id` + `confidence` |
| 时间旅行 | 不支持 | `effective_*_at(as_of_ts)` 任意时点回溯 |
| "忘记" | 距离衰减 / cut-off | 不会忘 — 是 DB row 不是相似度 |
| 写入复杂度 | 低 (chunk + embed) | 中 (LLM 输出 structured JSON) |
| 适用场景 | 长尾记任意话 | 业务字段已定义、需要可审计可回滚的 agent 改动 |

**两套不冲突**. 你的 app 如果同时需要"记任意话" + "可审计改动", 两套配合用 — vector 当语义索引, intent ledger 当事实账本.

## 核心抽象一图

```
                    ┌──────────────────────────────────────────────┐
   用户/Agent 说话 →  │            l15_change_intents (账本表)         │
                    │                                              │
                    │  kind         = PATCH|ASSERT|ANNOTATE|FLAG    │
                    │  status       = PROPOSED→APPLIED→SUPERSEDED  │
                    │                          |REJECTED|EXPIRED   │
                    │  source_layer = USER_DIRECT > L2_FORM >       │
                    │                 L2_CHAT > L2_VOICE >          │
                    │                 AGENT_INFERENCE               │
                    │  source_quote (原话截出来的证据)               │
                    │  confidence   (0–1)                           │
                    └────────────────────────┬─────────────────────┘
                                             │
                            effective_<entity>_at(p_as_of_ts)
                            ── PG SQL function 按时间戳重放 ──
                                             │
                                             ▼
                            ┌──────────────────────────────────────┐
                            │  effective_<entity>  视图 / 函数返回值   │
                            │  ("截至 p_as_of_ts 的真相")            │
                            └────────────────────┬─────────────────┘
                                                 ▼
                                  Agent system prompt 注入 snapshot
                                       (下一轮 LLM 看到)
```

## 5 分钟上手

按这个顺序读 + 改:

1. **`01-design.md`** — 先理解每个抽象解决什么问题 (20-30 min)
2. **`02-schema-template.sql`** — copy, 把 `-- TODO` 注释处换成你的实体表名 (10 min)
3. **`03-runtime-template.py`** — 应用层 helper, 业务字段全是占位符, 改完直接 import (15 min)
4. **`04-integration-guide.md`** — 接 LLM agent 的 system prompt 模板 + JSON 输出契约 + effect handler 写法 (15 min)

## 文件导航

| 文件 | 给谁读 | 形态 |
|---|---|---|
| README.md (本文) | 第一次看的人 | 总览 + 5 分钟决策 |
| 01-design.md | 想理解为什么这么设计 | 设计理念长文 |
| 02-schema-template.sql | 想直接改 schema 跑起来 | 可 copy PG DDL |
| 03-runtime-template.py | 写应用层代码 | 可 copy Python helper |
| 04-integration-guide.md | 接 LLM | 集成指南 |

## 何时**不**该用这套

- 用户说什么都想记 (开放对话, 长尾偏好) — 用 vector memory
- entity 形状不稳定, 一周改三次 schema — migration + `effective_*_at` 函数也要重写, 工程成本不值
- 只需要近似召回 / 模糊匹配 — 这是精确召回
- 单纯日志, 不需要"截至此刻的真相"合成 — append-only log 表就够

## 现状

- 这套设计基于关系数据库设计的 agent 记忆, 你看到的模板代码是以占位符字段提供的模板
- 文档全程用虚构 **TodoAgent** 举例 — 可替换为你的业务
- 你 copy 走自负责
