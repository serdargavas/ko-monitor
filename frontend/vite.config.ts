import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { VitePWA } from "vite-plugin-pwa";

// The FastAPI server started with `python -m ko_monitor run`.
const API_TARGET = "http://127.0.0.1:8765";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      // Our own service worker (src/sw.ts); the plugin only injects the precache file list.
      strategies: "injectManifest",
      srcDir: "src",
      filename: "sw.ts",
      injectRegister: false, // src/main.tsx registers /sw.js itself
      manifest: false, // public/manifest.webmanifest is copied as is
      injectManifest: {
        globPatterns: ["**/*.{html,js,css,png,webmanifest}"],
      },
      devOptions: { enabled: false },
    }),
  ],
  build: {
    // FastAPI serves web/ unchanged; the build output is committed.
    outDir: "../web",
    emptyOutDir: true,
  },
  server: {
    proxy: {
      "/api": {
        target: API_TARGET,
        ws: true, // WS /api/stream
        // The server checks Host (TrustedHostMiddleware) and Origin == Host (POSTs, WebSocket).
        changeOrigin: true,
        headers: { origin: API_TARGET },
      },
    },
  },
});
