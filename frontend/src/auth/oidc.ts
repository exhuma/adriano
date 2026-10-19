/**
 * OIDC public-client setup (`module-auth-oidc-vue`): Authorization
 * Code + PKCE via `oidc-client-ts`, configured only when runtime
 * config supplies an authority and a client id.
 *
 * Token storage: the signed-in `User` (which carries the access and
 * refresh tokens) is kept in `userStore`, backed by
 * `InMemoryWebStorage` -- never `localStorage`, which RFC 8252 / BCP
 * 212 flags as persistently exposed to XSS. This means a full page
 * reload signs the user out (there is nothing to restore from); that
 * is an accepted, documented trade-off applied consistently to both
 * OIDC and dev-login sessions (see `src/auth/devAuth.ts`).
 *
 * `stateStore` is deliberately left at its library default
 * (`sessionStorage`): it holds only the short-lived PKCE verifier,
 * nonce, and return-path for the few seconds of the full-page
 * redirect round trip to the identity provider and back -- never a
 * token -- and it *must* survive that round trip, which an in-memory
 * store cannot (the page is fully reloaded when the IdP redirects
 * back). Memory-only state would make `signinRedirectCallback` fail
 * every time.
 */
import { InMemoryWebStorage, UserManager, WebStorageStateStore } from "oidc-client-ts";

import {
  oidcAuthority,
  oidcClientId,
  oidcConfigured,
  oidcPostLogoutRedirectUri,
  oidcRedirectUri,
  oidcScope,
} from "@/config";

let manager: UserManager | null = null;

if (oidcConfigured) {
  manager = new UserManager({
    authority: oidcAuthority!,
    client_id: oidcClientId!,
    redirect_uri: oidcRedirectUri!,
    post_logout_redirect_uri: oidcPostLogoutRedirectUri,
    scope: oidcScope,
    response_type: "code",
    // oidc-client-ts v3 renews automatically (refresh token when the
    // IdP issued one via the `offline_access` scope, otherwise a
    // silent iframe renewal) -- there is no separate
    // "useRefreshTokens" setting in this major version.
    automaticSilentRenew: true,
    userStore: new WebStorageStateStore({ store: new InMemoryWebStorage() }),
  });
}

/**
 * The configured `UserManager`, or `null` when OIDC is not
 * configured for this deployment.
 *
 * :returns: The singleton `UserManager`, or `null`.
 */
export function getUserManager(): UserManager | null {
  return manager;
}

/** Whether OIDC sign-in can be offered (an authority and client id
 *  are configured). Re-exported from `config.ts` for convenience. */
export { oidcConfigured };
