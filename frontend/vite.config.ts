/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// DESPORTO_API_PORT / DESPORTO_UI_PORT let a second dev stack run next to a game in progress.
const api = process.env.DESPORTO_API_PORT ?? "8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: Number(process.env.DESPORTO_UI_PORT ?? 5173),
    proxy: {
      "/api": `http://127.0.0.1:${api}`,
      "/ws": { target: `ws://127.0.0.1:${api}`, ws: true },
    },
  },
  test: {
    setupFiles: ["src/test-setup.ts"],
  },
});
