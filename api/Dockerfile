# syntax=docker/dockerfile:1
#
# crm-api 镜像 (FastAPI 后端). 构建上下文 = 仓库根 (需同时访问 memory-ledger 库源码
# 与 api/ 源码), 见 docker-compose.yml 的 build.context。
#
# 多阶段 + 依赖层与源码层分离: 第三方依赖单独成层先装, 改业务代码不重装。

ARG PYTHON_VERSION=3.12

# ---------------------------------------------------------------- builder ----
FROM python:${PYTHON_VERSION}-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 1) 第三方运行时依赖 (缓存层, 与源码解耦)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install \
        "fastapi>=0.115" "uvicorn[standard]>=0.30" "anthropic>=0.40" \
        "psycopg[binary]>=3.1" "psycopg-pool>=3.2"

# 2) 安装 memory-ledger 库 (本地 monorepo, 只 COPY 构建必需文件)
COPY pyproject.toml README.md LICENSE NOTICE ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/pip pip install --no-deps .

# 3) 安装 crm-api (依赖已就位 → --no-deps)
COPY api/pyproject.toml ./api/
COPY api/src ./api/src
RUN --mount=type=cache,target=/root/.cache/pip pip install --no-deps ./api

# ---------------------------------------------------------------- runtime ----
FROM python:${PYTHON_VERSION}-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

RUN useradd --create-home --uid 10001 app
COPY --from=builder /opt/venv /opt/venv
USER app

EXPOSE 8000
# DATABASE_URL / ANTHROPIC_API_KEY / MEMORY_LEDGER_MODEL 由 compose 注入。
CMD ["uvicorn", "crm_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
