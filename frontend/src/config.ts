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
 * `window.__APP_CONFIG__`. In local dev that global is the static stub
 * in `public/config.js` (usually empty), and the
 * `import.meta.env.VITE_*` build-time values are used instead.
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
  /** OIDC discovery/authority base URL. Unset: OIDC sign-in is not
   *  offered (the app may still work via the gated dev login). */
  oidcAuthority?: string;
  /** OIDC public client id registered at the authority. */
  oidcClientId?: string;
  /** Redirect URI registered at the IdP for the authorization code
   *  callback (must resolve to the app's `/auth/callback` route). */
  oidcRedirectUri?: string;
  /** Redirect URI the IdP sends the browser to after sign-out. */
  oidcPostLogoutRedirectUri?: string;
  /** OIDC scopes requested at sign-in. */
  oidcScope?: string;
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

/** OIDC discovery/authority base URL, or `undefined` when OIDC is
 *  not configured for this deployment (runtime wins over the
 *  `VITE_OIDC_AUTHORITY` local-dev fallback). */
export const oidcAuthority: string | undefined =
  runtime.oidcAuthority || import.meta.env.VITE_OIDC_AUTHORITY || undefined;

/** OIDC public client id, or `undefined` when OIDC is not
 *  configured. */
export const oidcClientId: string | undefined =
  runtime.oidcClientId || import.meta.env.VITE_OIDC_CLIENT_ID || undefined;

/** Registered redirect URI for the authorization code callback. */
export const oidcRedirectUri: string | undefined =
  runtime.oidcRedirectUri ||
  import.meta.env.VITE_OIDC_REDIRECT_URI ||
  (typeof window !== "undefined"
    ? `${window.location.origin}/auth/callback`
    : undefined);

/** Redirect URI the IdP sends the browser to after sign-out. */
export const oidcPostLogoutRedirectUri: string | undefined =
  runtime.oidcPostLogoutRedirectUri ||
  import.meta.env.VITE_OIDC_POST_LOGOUT_REDIRECT_URI ||
  (typeof window !== "undefined" ? window.location.origin : undefined);

/** OIDC scopes requested at sign-in. Optional: defaults when unset,
 *  so it is not treated as "required" config. */
export const oidcScope: string =
  runtime.oidcScope || import.meta.env.VITE_OIDC_SCOPE || "openid profile email";

/** Whether enough OIDC configuration is present to offer OIDC
 *  sign-in. Both an authority and a client id are required; a
 *  deployment may legitimately omit OIDC entirely and rely only on
 *  the gated dev login (or on no auth at all, reported by
 *  `/healthz`). */
export const oidcConfigured: boolean = Boolean(oidcAuthority && oidcClientId);

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
