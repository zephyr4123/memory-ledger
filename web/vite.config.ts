import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// /api 代理与 HMR 经环境变量注入 (见 compose.dev.yml); 本地裸跑 dev 用默认值。
// 经 globalThis 取 process.env, 免为一个配置文件装 @types/node。
const env =
  (globalThis as { process?: { env?: Record<string, string | undefined> } }).process?.env ?? {};
const apiTarget = env.VITE_API_PROXY ?? "http://localhost:8000";
const hmrClientPort = env.VITE_HMR_CLIENT_PORT ? Number(env.VITE_HMR_CLIENT_PORT) : undefined;
const usePolling = env.VITE_USE_POLLING === "true";

// 本地 dev: 把 /api 代理到后端; Docker 生产镜像改由 nginx 反代 (见 nginx.conf)。
// Docker dev 模式 (compose.dev.yml): 代理指向 api 容器, HMR 走宿主映射端口, 开轮询监听。
export default defineConfig({
  plugins: [react()],
  server: {
    host: true, // 监听所有网卡 —— 容器内 dev server 必须
    proxy: {
      "/api": {
        target: apiTarget,
        changeOrigin: true,
      },
    },
    ...(hmrClientPort ? { hmr: { clientPort: hmrClientPort } } : {}),
    ...(usePolling ? { watch: { usePolling: true } } : {}),
  },
});
