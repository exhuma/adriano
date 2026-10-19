import { fileURLToPath, URL } from "node:url";

import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vite";
import vuetify from "vite-plugin-vuetify";

// Dev-only proxy target for the FastAPI backend (see DECISIONS.md:
// backend on 8100, Vite dev server on 5173).
const backendDevUrl = "http://localhost:8100";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue(), vuetify({ autoImport: true })],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    proxy: {
      "/api": backendDevUrl,
      "/healthz": backendDevUrl,
    },
  },
});
