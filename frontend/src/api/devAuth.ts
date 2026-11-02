/**
 * The dev-only endpoints (dev login and the catalog's role names),
 * isolated from `src/api/auth.ts` on purpose: this module
 * (and everything that imports it) is reachable
 * **only** through `src/auth/devAuth.ts` -> the dynamically-imported
 * `DevLoginDialog`, so a production build's dead-code elimination
 * can drop the dev-login mechanism -- including these endpoint paths
 * -- entirely (`module-dev-auth-bypass`). Both paths are markers in
 * `scripts/check-no-dev-auth.sh`. Do not import this module
 * from anywhere that is itself unconditionally bundled (e.g.
 * `src/composables/useAuth.ts`).
 */
import { api } from "@/api";
import type { DevLoginIn, DevRolesOut } from "@/types/auth";

/**
 * Create a dev session for the requested identity. The backend
 * answers 204 and sets the session cookie; the caller then re-runs
 * the session check.
 *
 * Opts out of the re-auth loop guard: it is a sign-in, not an API
 * call the session authorised.
 *
 * :param identity: Subject, name, email, and roles to assert.
 * :throws ApiError: `503 auth_unconfigured` if dev auth has no
 *     session key.
 */
export async function createDevSession(identity: DevLoginIn): Promise<void> {
  await api.post<null>("/auth/dev/login", identity, { trackAuth: false });
}

/**
 * List the loaded catalog's role names for the dev sign-in presets.
 *
 * :returns: The `rbac` roles with their permissions and the
 *     approval-policy reviewer roles.
 * :throws ApiError: `404` when the backend has dev auth disabled.
 */
export function listDevRoles(): Promise<DevRolesOut> {
  return api.get<DevRolesOut>("/auth/dev/roles", { trackAuth: false });
}
