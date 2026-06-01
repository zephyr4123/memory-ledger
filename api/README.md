# crm-api —— memory-ledger Personal-CRM 的 FastAPI 后端

把 memory-ledger 的账本能力 + 一个**真 LLM extractor** 编排成对话式 HTTP API。
它是库的一个**驱动适配器**(与 CLI 平级):库核心保持 LLM 无关、零依赖;真 LLM
(Claude)只是库 `Extractor` 端口的具体实现,住在 `crm_api.extraction`。

## 一轮对话怎么走

```
POST /api/turns  (SSE)
  用户一句话
   → 取当前记忆 snapshot 注入 LLM
   → Claude 流式回复 (event: reply_delta) + 通过 tool-use 吐结构化 4-kind intent
   → 低危 (ASSERT/ANNOTATE/FLAG) 直落; 高危 PATCH → PROPOSED 待确认
   → event: done { banners, person(刷新后真相), ledger(账本流水) }
```

确认闸门:`POST /api/intents/confirm`（采纳)/ `POST /api/intents/reject`（驳回)。

## 端点

| 方法 | 路径 | 作用 |
|---|---|---|
| GET | `/api/health` | 存活 + 当前 LLM 模式 (`live`/`mock`) |
| POST | `/api/turns` | 对话一轮 (SSE 流式) |
| GET | `/api/people` | 联系人列表 |
| GET | `/api/people/{id}?as_of=<ISO>` | 某联系人截至某时点的真相(**时光机**) |
| GET | `/api/people/{id}/ledger` | 原始 intent 流水(**审计时间轴 + 逐字溯源**) |
| POST | `/api/intents/confirm` | 采纳待确认改动 |
| POST | `/api/intents/reject` | 驳回待确认改动 |

## 环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `DATABASE_URL` | `postgresql://memory_ledger:memory_ledger@localhost:5432/memory_ledger` | Postgres DSN |
| `ANTHROPIC_API_KEY` | (空) | **配了才是真 LLM (live)**;没配则离线降级 (mock, 不写记忆) |
| `MEMORY_LEDGER_MODEL` | `claude-sonnet-4-6` | 对话模型 |
| `CRM_USER_ID` | `u1` | 多租户 owner id |
| `CORS_ORIGINS` | `localhost:5173,4173,80` | 允许的前端来源(逗号分隔) |

## 本地跑

```bash
pip install -e './api[dev]'                 # memory-ledger 需已在同环境
export DATABASE_URL=postgresql://localhost/mydb
export ANTHROPIC_API_KEY=sk-ant-...         # 不配则 mock 模式
uvicorn crm_api.main:app --reload

pytest api/tests/                            # testcontainers + FakeExtractor, 不打真网络
```

> 正式编排见仓库根 `docker-compose.yml`(`api` 服务)。
