/**
 * The dev-only token endpoint, isolated from `src/api/auth.ts` on
 * purpose: this module (and everything that imports it) is reachable
 * **only** through `src/auth/devAuth.ts` -> the dynamically-imported
 * `DevLoginDialog`, so a production build's dead-code elimination
 * can drop the dev-login mechanism -- including this endpoint path
 * -- entirely (`module-dev-auth-bypass`). Do not import this module
 * from anywhere that is itself unconditionally bundled (e.g.
 * `src/composables/useAuth.ts`).
 */
import { api } from "@/api";
import type { DevTokenIn, DevTokenOut } from "@/types/auth";

/**
 * Mint a dev-only HS256 token for the requested identity.
 *
 * :param identity: Subject, name, email, and roles to assert.
 * :returns: The minted access token and its lifetime.
 * :throws ApiError: `503 auth_unconfigured` if the backend secret is
 *     unset.
 */
export function createDevToken(identity: DevTokenIn): Promise<DevTokenOut> {
  return api.post<DevTokenOut>("/auth/dev/token", identity);
}
