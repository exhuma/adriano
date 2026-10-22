import { fileURLToPath, URL } from "node:url";

import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vite";
import vuetify from "vite-plugin-vuetify";

// Dev-only proxy target for the FastAPI backend (backend on 8100, Vite
// dev server on 5173). Overridable so `task demo:ui` can point the same
// dev server at the docker-compose demo container (which serves the
// API and the SPA on one published port) instead.
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
      // Backend-for-Frontend auth routes: sign-in redirect and
      // callback, session check, sign-out, and (dev only) dev login.
      // The backend is the OIDC client; the SPA has no
      // `/auth/callback` route of its own. Proxied as-is: leave
      // `changeOrigin` at its default (`false`) so the browser's
      // `Host` and `Origin` still match and the backend's CSRF
      // origin check passes.
      "/auth": backendDevUrl,
      // Runtime config (`window.__APP_CONFIG__`), rendered by the
      // backend, wins over the empty stub in `public/`.
      "/config.js": backendDevUrl,
    },
  },
});
