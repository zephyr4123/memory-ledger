import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// 本地 dev: 把 /api 代理到后端 (Docker 里改由 nginx 反代, 见 nginx.conf)。
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
