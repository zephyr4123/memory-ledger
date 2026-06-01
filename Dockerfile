# syntax=docker/dockerfile:1
#
# memory-ledger 应用镜像 (库 + CLI + Personal-CRM demo).
#
# 多阶段构建:
#   builder  —— 建独立 venv, 装依赖, 从 src 构建并安装本包
#   runtime  —— 只搬装好的 venv + examples, 不含编译工具链 → 镜像小、攻击面小
#
# 缓存策略: 重依赖 (psycopg) 单独成层先装, 再装本包源码 → 改业务代码不会重装 psycopg.

ARG PYTHON_VERSION=3.12

# ---------------------------------------------------------------- builder ----
FROM python:${PYTHON_VERSION}-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore

# 独立 venv: 整体拷给 runtime, 干净可移植 (不污染系统 site-packages).
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 1) 先装运行期重依赖. psycopg[binary] 自带 libpq, 无需 apt 装编译器/库 →
#    单独成一层, 只要依赖不变就命中缓存.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install "psycopg[binary]>=3.1"

# 2) 再构建并安装本包. 只 COPY 构建必需文件 (pyproject 引用了 README/LICENSE/NOTICE),
#    --no-deps 因为依赖上一层已装好, 避免重复解析.
COPY pyproject.toml README.md LICENSE NOTICE ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-deps .

# ---------------------------------------------------------------- runtime ----
FROM python:${PYTHON_VERSION}-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

# 非 root 运行 (最小权限).
RUN useradd --create-home --uid 10001 app

# 只搬装好的 venv: 含 memory_ledger + psycopg + 包内 bundled SQL, 无构建工具链.
COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
# examples 按设计不进 wheel; demo 以 `python -m` 跑需源码在 sys.path, 单独拷入.
COPY --chown=app:app examples ./examples

USER app

# 默认入口: 跑 Personal-CRM demo (compose 注入 DATABASE_URL, 自身幂等 apply 迁移).
# 其它入口由 compose/run 覆盖, 例如:
#   docker compose run --rm app memory-ledger init-db "$DATABASE_URL"
#   docker compose run --rm app bash
CMD ["python", "-m", "examples.personal_crm.run_demo"]
