import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// During local dev, proxy API + WS to the backend so the SPA can use
// same-origin relative paths (/api, /ws) exactly like in production.
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
      "/ws": { target: "ws://localhost:8000", ws: true },
      "/media": { target: "http://localhost:8000", changeOrigin: true },
      "/static": { target: "http://localhost:8000", changeOrigin: true },
      // Same-origin live video (mirrors the production nginx config)
      "/webrtc": {
        target: "http://localhost:8889",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/webrtc/, ""),
      },
      "/hls": {
        target: "http://localhost:8888",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/hls/, ""),
      },
    },
  },
});
