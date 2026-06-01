# syntax=docker/dockerfile:1
#
# web 镜像: node 多阶段构建静态产物 → nginx 服务 + 反代 /api。
# 构建上下文 = 仓库根 (与 api 一致), 见 docker-compose.yml。

ARG NODE_VERSION=20

# ---------------------------------------------------------------- builder ----
FROM node:${NODE_VERSION}-alpine AS builder
WORKDIR /app

# 依赖层 (package.json 不变则命中缓存)
COPY web/package.json web/package-lock.json* ./
RUN --mount=type=cache,target=/root/.npm npm install

# 源码 → 构建
COPY web/ ./
RUN npm run build

# ---------------------------------------------------------------- runtime ----
FROM nginx:1.27-alpine AS runtime
COPY web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
