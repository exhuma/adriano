/**
 * Typed runtime configuration (module-runtime-config-spa).
 *
 * This is the only module that reads `window.__APP_CONFIG__` or
 * `import.meta.env`. Components must import named values from here
 * instead of reading either source directly, so one built artefact
 * can be deployed to any environment without a rebuild.
 *
 * In a deployed container, the entrypoint renders `config.js` from
 * environment variables before the app bundle loads, populating
 * `window.__APP_CONFIG__`. In local dev that global is the static
 * stub in `public/config.js` (usually empty), and the
 * `import.meta.env.VITE_*` build-time values are used instead.
 */

/** Shape of the config injected as `window.__APP_CONFIG__`. */
interface RuntimeConfig {
  /** Base URL the API client prefixes onto every request path. */
  apiBaseUrl?: string;
}

declare global {
  interface Window {
    __APP_CONFIG__?: RuntimeConfig;
  }
}

const runtime: RuntimeConfig = window.__APP_CONFIG__ ?? {};

/**
 * Base URL for API requests.
 *
 * The runtime-injected value wins; otherwise falls back to the
 * build-time `VITE_API_BASE_URL`, and finally to an empty string so
 * requests resolve as same-origin relative paths (the dev proxy and
 * the production deployment both serve the API from the same
 * origin as the SPA).
 */
export const apiBaseUrl: string =
  runtime.apiBaseUrl ?? import.meta.env.VITE_API_BASE_URL ?? "";
