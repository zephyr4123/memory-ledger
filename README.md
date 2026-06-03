<div align="center">

# Memory Ledger

### 基于关系数据库的 Agent 记忆方案 —— 以账本记录,而非向量嵌入

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE) &nbsp;![PostgreSQL 16](https://img.shields.io/badge/PostgreSQL-16-336791?logo=postgresql&logoColor=white) &nbsp;![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white) &nbsp;![React 18](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)

<p>
每次陈述记为一条 <b>typed intent</b> 写入单张<b>账本表</b>;<br>
由纯 <b>SQL 函数</b>按时间戳<b>确定性重放</b>出任意时刻的真相。<br>
<sub>读路径不含向量与 LLM · 易于扩展到你自己的业务 · 非 RAG / 向量 / 知识图谱</sub>
</p>

<table>
<tr>
<td align="center">❌ &nbsp;<b>vector-first(主流)</b></td>
<td align="center">✅ &nbsp;<b>relational-first(本方案)</b></td>
</tr>
<tr>
<td align="center">记忆存入 embedding 近似索引<br><sub>非确定 · 随模型漂移 · 难精确查询 · 不可读</sub></td>
<td align="center">记忆即关系表中的<b>账本行</b><br><sub>确定性 SQL · 可时间旅行 · 可审计</sub></td>
</tr>
</table>

<sub>🧾 同库账本 &nbsp;·&nbsp; ⏳ 确定性 as-of &nbsp;·&nbsp; 🚦 默认人工闸门 &nbsp;·&nbsp; 🔢 DB 强制 4-kind</sub>

</div>

---

## 💡 概述

<div align="center">
<img src="docs/concept/01-ledger-vs-vector.jpg" width="880" alt="记忆即账本行而非向量嵌入:向量雾 → 人工闸门 → 有序账本">
<br><sub>弥散的向量近似(左)经一道人工闸门(中),收敛为同库可查、可重放的<b>有序账本真相</b>(右)</sub>
</div>

每一次**事实陈述 / 改字段 / 注释 / 标疑**记为一条 intent,写入账本表 `l15_change_intents`。SQL 函数 `effective_*_at(as_of)` 再按时间戳重放出"截至此刻的真相"。

> 跨会话记忆依赖 **SQL 与时间戳**,而非 embedding 与相似度。

- **设计与参考实现** —— 分层架构,账本核心与业务实体解耦。
- **易于扩展** —— 换成你自己的业务表,核心逻辑原样复用。
- **示例皆虚构** —— TodoAgent 贯穿文档,「念念手记」仅为可视化外壳。

---

## ⚖️ 关系数据库,而非 embedding

记忆即关系表中的**账本行**,召回为确定性 SQL,读路径不含向量。主流 `vector-first` 则以独立 embedding 索引承载记忆。

> 差异不在**用不用数据库**(Letta、Mem0 同样跑 Postgres,存的却是向量),而在**关系库为主体、SQL 为召回、读路径无 embedding**。

<div align="center">
<img src="docs/concept/02-relational-vs-vector.jpg" width="820" alt="左 SQL 精确命中一行,右 向量近似召回一片">
<br><sub>左:SQL <b>精确命中</b>某一行 &nbsp;·&nbsp; 右:向量索引只能给出<b>近似的一片</b> —— 确定 vs 漂移</sub>
</div>

本质是**对既有业务表的事件溯源**:intent 分 `PATCH` / `ASSERT` / `ANNOTATE` / `FLAG` 四类,由 Postgres `CHECK` 在存储层强制;账本与业务表同库共置、同事务一致。

### 与主流方案对照

| 维度 | 🔎 Vector Memory | 🕸️ 时序 KG | 🧾 **Memory Ledger** |
|---|---|---|---|
| **存储** | 自有向量库 | 自有图库 | **业务表同库 + 单账本表** |
| **召回** | embedding 近似 | 向量 + 图 + 重排 | **纯 SQL,无 embedding / LLM** |
| **确定性** | ❌ | ❌ | ✅ **bit-for-bit 可复现** |
| **时间旅行** | ❌ | 🟡 事实区间 | ✅ **任意时点整体重放** |
| **改口撤回** | 覆盖 | 失效非删 | **supersede 链,可回滚** |
| **人工闸门** | ❌ | ❌ | ✅ **默认:改字段须确认** |
| **出处** | 薄 | episode | **逐字 quote + 分级 + 仲裁** |
| **强类型** | 无 / 可选 | 应用层 ontology | ✅ **DB CHECK 强制固定 4-kind** |
| **与嵌入模型** | 换模型须重嵌入 | 须重嵌入 | **解耦,不重嵌入** |

> **边界** —— 各项单独均非首创(双时态 DB、Zep / Graphiti、Letta 各擅其一)。可防守处在**组合**:同库账本 × 确定性 as-of × 默认人工闸门 × DB 强制 4-kind 强出处,四者合一、开箱交付。

**互补**:向量作语义索引,Memory Ledger 作事实账本 —— 不争"记任意话",专司"可审计 / 可回滚 / 可时间旅行的结构化改动"。

---

## 🗺️ 核心抽象

intent 落账,再由 `effective_*_at(as_of)` 沿时间戳确定性重放,合成任意时刻的真相,供下一轮 LLM 取用。

<div align="center">
<img src="docs/concept/03-replay-pipeline.jpg" width="720" alt="四类 intent → 账本表 → 重放棱镜 → 当前真相 → LLM">
<br><sub>四类 intent 汇入<b>单张账本表</b> → 沿时间戳<b>确定性重放</b> → <b>截至此刻的真相</b> → 喂给下一轮 LLM</sub>
</div>

**账本行 `l15_change_intents` 的关键字段:**

| 字段 | 取值 / 含义 |
|---|---|
| `kind` | `PATCH` / `ASSERT` / `ANNOTATE` / `FLAG` —— DB `CHECK` 强制 4 类 |
| `status` | `PROPOSED → APPLIED → SUPERSEDED \| REJECTED \| EXPIRED`(5-state) |
| `source_layer` | `USER_DIRECT > L2_FORM > L2_CHAT > L2_VOICE > AGENT_INFERENCE`(权威递减) |
| `source_quote` | 逐字截取的原话证据 |
| `confidence` | `0–1` 把握度 |

---

## 🧠 作为 Agent Memory 基础设施

账本即一层 **Agent Memory 基础设施**:可精确查询的结构化账本,而非不可读的向量。

<div align="center">
<img src="docs/concept/04-thin-tools-thick-ledger.jpg" width="620" alt="薄工具层悬于结构化账本基底,一次查询拉起完整链条">
<br><sub><b>薄工具</b>(上)悬于<b>厚账本</b>基底(下);一次查询即拉起完整链条 —— 工具变薄,智能涌现</sub>
</div>

- **🪶 不预载记忆** —— 上下文不 dump 记忆;一次工具调用即取回完整画像:真相、溯源、存疑、变更链、任意时点。
- **🧰 工具变薄** —— 工具仅是账本读能力的轻包装,合成与重放归基础设施,新增工具近乎零成本。
- **✨ 智能涌现** —— 冷启动、零上下文,一次调用即得丰富历史,呈现"深知其详"的连续记忆;源自「基础设施 + 薄工具」,非堆上下文或精巧提示词。

---

## 🧭 确定性与人的判断

晚近的 agent 工程,**确定性执行**与**把人留在回路**正重新获得重视。Memory Ledger 与之相印证 —— 非追潮流,而是固有取向:

- **⚙️ 确定性** —— 召回是纯 SQL,bit-for-bit 可复现、可审计。
- **🤝 人机协同** —— 改字段须过人工闸门:agent 提议(`PROPOSED`)、人裁决(`APPLIED`),逐字出处供人复核。

<div align="center">
<img src="docs/concept/05-determinism-gate.jpg" width="840" alt="数据沿确定性轨道前行,改字段须经唯一人工闸门方生效,被拒者留痕">
<br><sub>数据沿<b>确定性轨道</b>前行,改字段须经唯一的<b>人工闸门</b>方才生效;被拒者留痕(红)</sub>
</div>

> 模型可以越来越强,但经验与判断仍属于人。

---

## 🎬 演示

账本本身不可见 —— 只是库中的行。下方借一个对话式 Personal-CRM 外壳演示:真实 `live` LLM(DeepSeek)运行,联系人 **林思颖**(产品经理 → CTO,公司 晨星 → 蓝湖 → Globex)。**外壳仅为演示,核心交付为上述设计。**

<div align="center">
<img src="web/public/img/brand/mascot.png" width="76" alt="小本">
<br><sub><b>「念念手记」· 助手「小本」</b> —— 数据库理念的可视化外壳</sub>
</div>

### 🧠 跨会话记忆

空白新线程问"她现在的职位",无任何上文,系统仍调 `get_contact` 答出 **CTO**。记忆按实体跨会话共享。

<div align="center">
<img src="docs/screenshots/05-cross-session-recall.jpg" width="860" alt="全新会话仍准确回忆 CTO">
<br><sub>左为新建空白线程 · 右为 Globex / CTO 人卡 · 无需上文即命中</sub>
</div>

### 🔧 流式工具调用

答前先流式检索(`get_contact` running → done)再作答 —— 确在查库,非前端预设。

<div align="center">
<img src="docs/screenshots/02-streaming-tools.jpg" width="820" alt="流式工具条 get_contact">
<br><sub>先检索、后作答 · 数据来自既往会话</sub>
</div>

### 🚦 确认闸门

"她升任 CTO 了"要改既有字段,底部弹出**确认闸门**,确认后方写入。

<div align="center">
<img src="docs/screenshots/03-confirm-gate.jpg" width="820" alt="确认闸门:职位 → CTO">
<br><sub>「职位 → CTO ‹暂不 / 确认›」· 未确认不进入生效真相(PROPOSED)</sub>
</div>

### 🧾 账本与溯源

右栏「变更记录」留存每次改动:左为 supersede 链,右为逐字溯源。

<div align="center">
<img src="docs/concept/07-supersede-provenance.jpg" width="780" alt="示意:新行 supersede 旧行成链,逐字出处与把握度随附,拒绝与待核实留痕">
<br><sub>📐 <b>示意</b> · 新行 supersede 旧行成链,逐字出处与把握度随附;拒绝 / 待核实同样留痕</sub>
</div>

<div align="center">
<table>
<tr>
<td align="center"><img src="docs/screenshots/06-ledger-chain.jpg" width="398" alt="变更链:Globex ← 蓝湖科技 ← 晨星科技"></td>
<td align="center"><img src="docs/screenshots/06-ledger-provenance.jpg" width="398" alt="逐字溯源:原话 + 把握度 + 来源"></td>
</tr>
<tr>
<td align="center"><sub>📜 <b>变更链</b>:Globex ← 蓝湖 ← 晨星(supersede)</sub></td>
<td align="center"><sub>🔍 <b>逐字溯源</b>:原话 + 把握 100% + 来源层级</sub></td>
</tr>
</table>
</div>

### ⏳ as-of 时光机

拖动时间轴,人卡重建该时刻的真相:晨星 → 蓝湖 → Globex,各由当时的 N 条记录经 `effective_*_at` 合成。

<div align="center">
<img src="docs/concept/06-time-travel.jpg" width="700" alt="示意:同一卡随时间由 1/2/4 条记录确定性重建">
<br><sub>📐 <b>示意</b> · 拖动时间轴,同一张卡由当时的 <b>1 / 2 / 4</b> 条记录确定性重建</sub>
</div>

<div align="center">
<table>
<tr>
<td align="center" width="33%"><img src="docs/screenshots/07-time-travel-1-origin.jpg" width="240" alt="时光机:晨星科技"></td>
<td align="center" width="33%"><img src="docs/screenshots/07-time-travel-2-mid.jpg" width="240" alt="时光机:蓝湖科技"></td>
<td align="center" width="33%"><img src="docs/screenshots/07-time-travel-3-now.jpg" width="240" alt="时光机:Globex"></td>
</tr>
<tr>
<td align="center"><sub><b>晨星</b> · 1 条合成</sub></td>
<td align="center"><sub><b>蓝湖</b> · 2 条合成</sub></td>
<td align="center"><sub><b>Globex</b> · 4 条合成</sub></td>
</tr>
</table>
</div>

### 🚫 拒绝与存疑留痕

不止记成功改动 —— 被拒(REJECTED)与待核实(FLAG)同样可审计。

<div align="center">
<img src="docs/screenshots/08-rejected-flag.jpg" width="640" alt="未采纳 + 待核实">
<br><sub>「所在地 → 柏林」未采纳 ·「搬迁待核实」· 5-state 状态机全程留痕</sub>
</div>

### 💭 深度思考

开启后先流式展开推理,再收束为结构化建议;接后端 reasoning 链路。

<div align="center">
<table>
<tr>
<td align="center"><img src="docs/screenshots/04-deep-thinking-1.jpg" width="410" alt="深度思考过程展开"></td>
<td align="center"><img src="docs/screenshots/04-deep-thinking-2.jpg" width="410" alt="深度思考收束为建议"></td>
</tr>
<tr>
<td align="center"><sub>推理流式展开</sub></td>
<td align="center"><sub>收束为建议</sub></td>
</tr>
</table>
</div>

---

## 🐳 本地运行

仅需 Docker:

```bash
cp .env.example .env       # 填 LLM_API_KEY 走真 LLM; 不填则 mock
docker compose up --build  # 起 db + api + web
# 打开 http://localhost:8080
docker compose down -v     # 清掉 (含数据卷)
```

| 服务 | 端口 | 说明 |
|---|---|---|
| `web` | 8080 | React 前端(nginx + 反代 `/api`) |
| `api` | 8000 | FastAPI(SSE 对话 / 时光机 / 账本 / 闸门) |
| `db` | 5433 | Postgres |

> 不配 `LLM_API_KEY` 也能启动:seed / 时光机 / 溯源 / 账本均可看,仅对话走 mock。换模型改三个环境变量即可(经 LiteLLM,见 `.env.example`)。
>
> 命令行 demo:`docker compose --profile demo run --rm demo`;含 103 个测试(`pytest` + testcontainers)。

---

## 🚧 不适用场景

- **任意开放内容**(长尾偏好)—— 宜用 vector memory。
- **形状不稳定的 entity** —— migration 与 `effective_*_at` 须同步重写,不划算。
- **仅需近似召回 / 模糊匹配** —— 本方案为精确召回。
- **仅需日志** —— append-only 日志表已足够。

---

## 📌 说明

- 示例实体与数据均为虚构占位(TodoAgent / 念念手记),替换为你自己的业务实体即可扩展。
- 复用风险自负。

---

## 📮 联系

<div align="center">

[![Email](https://img.shields.io/badge/Email-huangsuxiang5%40gmail.com-EA4335?logo=gmail&logoColor=white)](mailto:huangsuxiang5@gmail.com) &nbsp;![WeChat](https://img.shields.io/badge/WeChat-13976457218-07C160?logo=wechat&logoColor=white) &nbsp;![QQ](https://img.shields.io/badge/QQ-1736672988-12B7F5?logo=tencentqq&logoColor=white)

</div>

---

## 📄 开源协议

本项目以 **[Apache License 2.0](LICENSE)** 开源,详见 [`LICENSE`](LICENSE) 与 [`NOTICE`](NOTICE)。
