// Committed template for the deployed container's runtime config
// (module-runtime-config-spa). Phase 08's nginx entrypoint renders
// this into `config.js` (served at `/config.js`, loaded before the
// app bundle -- see `index.html`) by substituting the placeholders
// below from container environment variables, e.g. with `envsubst`:
//
//   envsubst < config.template.js > /usr/share/nginx/html/config.js
//
// Env var -> config key mapping (all optional; an unset/empty value
// falls through to "OIDC not configured" -- see `src/config.ts`):
//
//   API_BASE_URL                   -> apiBaseUrl
//   OIDC_AUTHORITY                 -> oidcAuthority
//   OIDC_CLIENT_ID                 -> oidcClientId
//   OIDC_REDIRECT_URI              -> oidcRedirectUri
//   OIDC_POST_LOGOUT_REDIRECT_URI  -> oidcPostLogoutRedirectUri
//   OIDC_SCOPE                     -> oidcScope
//
// SECURITY BOUNDARY: the dev-login gate (`VITE_DEV_AUTH`) is
// deliberately absent from this template and from `RuntimeConfig`
// (`src/config.ts`). It is a build-time literal baked into the
// frontend bundle at build time (`import.meta.env.DEV`, always
// `false` in a production build) -- no container environment
// variable can turn dev login on in a deployed image. Do not add it
// here.
window.__APP_CONFIG__ = {
  apiBaseUrl: "${API_BASE_URL}",
  oidcAuthority: "${OIDC_AUTHORITY}",
  oidcClientId: "${OIDC_CLIENT_ID}",
  oidcRedirectUri: "${OIDC_REDIRECT_URI}",
  oidcPostLogoutRedirectUri: "${OIDC_POST_LOGOUT_REDIRECT_URI}",
  oidcScope: "${OIDC_SCOPE}",
};
