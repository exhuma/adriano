// Local-development runtime config stub (module-runtime-config-spa).
//
// In the deployed image the backend serves `/config.js` itself,
// rendered from its `ADRIANO_*` settings (`backend/app/web.py`), and
// this copied stub is never reached. In local dev the Vite dev server
// proxies `/config.js` to the backend (`vite.config.ts`), so this
// stub only applies when the backend is not running.
//
// Deliberately empty. The dev-login gate (`VITE_DEV_AUTH`) is never
// part of this object (see `src/config.ts`): it is a build-time
// literal, not runtime config.
window.__APP_CONFIG__ = {};
