// Local-development runtime config stub (module-runtime-config-spa).
//
// In the deployed image the backend serves `/config.js` itself,
// rendered from its `ADRIANO_*` settings (`backend/app/web.py`), and
// this copied stub is never reached. In local dev it is served as-is
// by Vite from `public/`; `src/config.ts` falls back to
// `import.meta.env.VITE_*` for any key left unset here.
//
// Deliberately empty: local dev configures OIDC (if any) and the API
// base URL through `VITE_*` env vars / `.env.local`, never here. The
// dev-login gate (`VITE_DEV_AUTH`) is never part of this object (see
// `src/config.ts`): it is a build-time literal, not runtime config.
window.__APP_CONFIG__ = {};
