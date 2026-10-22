/**
 * Typed runtime configuration (module-runtime-config-spa).
 *
 * This is the only module that reads `window.__APP_CONFIG__` or
 * `import.meta.env`. Components must import named values from here
 * instead of reading either source directly, so one built artefact
 * can be deployed to any environment without a rebuild.
 *
 * In a deployed container, the backend renders `/config.js` from its
 * ADRIANO_* settings before the app bundle loads, populating
 * `window.__APP_CONFIG__`. In local dev the Vite dev server proxies
 * `/config.js` to the backend, so the same values apply; if the
 * backend is down the global stays empty and the defaults below
 * (plus the `import.meta.env.VITE_*` build-time values) are used.
 *
 * SECURITY BOUNDARY: `devAuthEnabled` is a separate, build-time-only
 * literal (see below) and is deliberately **not** part of
 * `RuntimeConfig`. The runtime-config mechanism can never turn on the
 * dev-login UI by injecting a value into `window.__APP_CONFIG__`
 * (`module-dev-auth-bypass`, `module-runtime-config-spa` "Never
 * expose security-sensitive toggles through runtime config").
 */

/** Shape of the config injected as `window.__APP_CONFIG__`. */
interface RuntimeConfig {
  /** Base URL the API client prefixes onto every request path. */
  apiBaseUrl?: string;
  /** Whether the backend has OIDC sign-in configured. Unset or
   *  `false`: no "Sign in" button is offered (the app may still work
   *  via the gated dev login). The OIDC client itself lives in the
   *  backend; the browser needs no IdP settings. */
  oidcEnabled?: boolean;
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

/** Whether the backend offers OIDC sign-in (`/auth/login`). */
export const oidcEnabled: boolean = runtime.oidcEnabled === true;

/**
 * Dev-login opt-in gate (`module-dev-auth-bypass`).
 *
 * `import.meta.env.DEV` is Vite's statically-replaced dev flag: it
 * is `true` only under the dev server and is replaced with the
 * literal `false` in any production build, so the bundler dead-code
 * eliminates the dev-login UI and helpers from production artefacts
 * regardless of how `VITE_DEV_AUTH` is set. `VITE_DEV_AUTH==='true'`
 * is the explicit developer opt-in, so dev login stays off by
 * default even under the dev server. This is a build-time literal,
 * never read from `RuntimeConfig`/`window.__APP_CONFIG__`.
 */
export const devAuthEnabled: boolean =
  import.meta.env.DEV && import.meta.env.VITE_DEV_AUTH === "true";
