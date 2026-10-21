/**
 * The dev-only endpoints (token minting and the catalog's role
 * names), isolated from `src/api/auth.ts` on purpose: this module (and everything that imports it) is reachable
 * **only** through `src/auth/devAuth.ts` -> the dynamically-imported
 * `DevLoginDialog`, so a production build's dead-code elimination
 * can drop the dev-login mechanism -- including these endpoint paths
 * -- entirely (`module-dev-auth-bypass`). Both paths are markers in
 * `scripts/check-no-dev-auth.sh`. Do not import this module
 * from anywhere that is itself unconditionally bundled (e.g.
 * `src/composables/useAuth.ts`).
 */
import { api } from "@/api";
import type { DevRolesOut, DevTokenIn, DevTokenOut } from "@/types/auth";

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

/**
 * List the loaded catalog's role names for the dev sign-in presets.
 *
 * :returns: The `rbac` roles with their permissions and the
 *     approval-policy reviewer roles.
 * :throws ApiError: `404` when the backend has dev auth disabled.
 */
export function listDevRoles(): Promise<DevRolesOut> {
  return api.get<DevRolesOut>("/auth/dev/roles");
}
