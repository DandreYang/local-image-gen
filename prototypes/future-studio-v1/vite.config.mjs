import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const studioBackend = process.env.STUDIO_BACKEND_URL || "http://127.0.0.1:8765";
const fixtureMode = process.env.STUDIO_FIXTURE === "1";

export function isLoopbackAddress(address = "") {
  const normalized = String(address).toLowerCase();
  return normalized === "127.0.0.1" || normalized === "::1" || normalized === "::ffff:127.0.0.1";
}

const localStudioProxyGuard = {
  name: "local-studio-proxy-loopback-guard",
  configureServer(server) {
    server.middlewares.use((request, response, next) => {
      if (request.url?.startsWith("/studio-api") && !isLoopbackAddress(request.socket.remoteAddress)) {
        response.statusCode = 403;
        response.setHeader("Content-Type", "application/json; charset=utf-8");
        response.end(JSON.stringify({ success: false, error: "Studio proxy is local-only" }));
        return;
      }
      next();
    });
  },
};

export default defineConfig({
  define: {
    "import.meta.env.VITE_STUDIO_FIXTURE": JSON.stringify(fixtureMode),
  },
  build: {
    outDir: "dist/client",
  },
  optimizeDeps: {
    include: ["react", "react-dom/client"],
  },
  server: {
    host: "0.0.0.0",
    allowedHosts: ["terminal.local"],
    proxy: {
      "/studio-api": {
        target: studioBackend,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/studio-api/, ""),
      },
    },
    warmup: {
      clientFiles: ["./src/main.jsx"],
    },
  },
  plugins: [localStudioProxyGuard, react()],
});
