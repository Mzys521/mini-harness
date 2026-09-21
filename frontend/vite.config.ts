import { fileURLToPath, URL } from "node:url";

import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vite";

// The workspace is served by FastAPI at /ui (assets) and / (index.html),
// so the build is emitted straight into the packaged static directory.
export default defineConfig({
  base: "/ui/",
  plugins: [vue()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  build: {
    outDir: fileURLToPath(new URL("../harness/ui/static", import.meta.url)),
    emptyOutDir: true,
    assetsDir: "assets",
    sourcemap: false,
    chunkSizeWarningLimit: 900,
  },
  server: {
    port: 5173,
    proxy: {
      "/healthz": process.env.HARNESS_API_URL ?? "http://127.0.0.1:8008",
      "/v1": process.env.HARNESS_API_URL ?? "http://127.0.0.1:8008",
    },
  },
});
