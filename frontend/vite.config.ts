import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";

// Set by `fitbit serve --dev` so the proxy follows a non-default --port.
const apiPort = process.env.FITBIT_API_PORT ?? "8000";

export default defineConfig({
  plugins: [react()],
  build: {
    // Built into the Python package so `fitbit serve` can serve it directly.
    outDir: fileURLToPath(new URL("../src/fitbit_app/static", import.meta.url)),
    emptyOutDir: true,
    rollupOptions: {
      output: {
        // ECharts is most of the bundle: keep it in its own long-lived, cacheable chunk.
        // (Function form: only the ECharts modules we actually import are included.)
        manualChunks(id) {
          if (/[\\/]node_modules[\\/](echarts|zrender|echarts-for-react)[\\/]/.test(id)) {
            return "echarts";
          }
          return undefined;
        },
      },
    },
    // The ECharts chunk is ~550 kB even tree-shaken; it's served locally and cached.
    chunkSizeWarningLimit: 700,
  },
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: { "/api": `http://127.0.0.1:${apiPort}` },
  },
});
