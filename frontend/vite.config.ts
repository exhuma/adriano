import { fileURLToPath, URL } from "node:url";

import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vite";
import vuetify from "vite-plugin-vuetify";

// Dev-only proxy target for the FastAPI backend (see DECISIONS.md:
// backend on 8100, Vite dev server on 5173). Overridable so `task
// demo:ui` (phase 08) can point the same dev server at the
// docker-compose demo stack's frontend (which itself proxies to the
// containerised backend) instead, without a second published port.
const backendDevUrl =
  process.env.VITE_DEV_PROXY_TARGET ?? "http://localhost:8100";

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
      // Dev-only token endpoint (`POST /auth/dev/token`); mounted on
      // the backend only when `ADRIANO_DEV_AUTH_ENABLED` is set (see
      // DECISIONS.md "Auth"). Scoped to `/auth/dev`, not all of
      // `/auth`, so the SPA's own `/auth/callback` route (the OIDC
      // redirect target, served by the SPA itself via history
      // fallback) is never proxied to the backend.
      "/auth/dev": backendDevUrl,
    },
  },
});
