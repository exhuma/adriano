/**
 * Dev-login sign-in/out and role presets (`module-dev-auth-bypass`).
 *
 * This module -- and `src/api/devAuth.ts` and `src/auth/devPresets.ts`,
 * which it alone imports -- is reachable **only** through
 * `DevLoginDialog.vue`, which `App.vue`
 * loads via a dynamic `import()` gated by the same build-time
 * literal as `src/config.ts`'s `devAuthEnabled`
 * (`import.meta.env.DEV && import.meta.env.VITE_DEV_AUTH === 'true'`).
 * In a production build that literal folds to `false`, so the
 * bundler's dead-code elimination drops this module, its import of
 * `src/api/devAuth.ts`, and the `/auth/dev/token` and
 * `/auth/dev/roles` endpoint paths entirely -- not merely hides them behind a runtime check. Do not
 * import this module from `src/composables/useAuth.ts` or any other
 * unconditionally-bundled module; that would defeat the isolation.
 */
import { createDevToken, listDevRoles } from "@/api/devAuth";
import { deriveDevPresets, type DevRolePreset } from "@/auth/devPresets";
import { clearDevSession, setDevSession } from "@/composables/useAuth";
import type { DevTokenIn } from "@/types/auth";

export type { DevRolePreset } from "@/auth/devPresets";

/**
 * Sign in through the gated dev-login flow: mint a token for the
 * requested identity and load `/me`.
 *
 * :param identity: Subject, name, email, and roles to assert.
 * :throws ApiError: `503 auth_unconfigured` if the backend secret is
 *     unset.
 */
export async function devSignIn(identity: DevTokenIn): Promise<void> {
  const token = await createDevToken(identity);
  await setDevSession(token.access_token);
}

/** Drop the dev-login token and cached identity. */
export function devSignOut(): void {
  clearDevSession();
}

/**
 * Load the dev sign-in presets that match the loaded catalog.
 *
 * :returns: Reader/Reviewer/Operator presets the catalog can satisfy.
 * :throws ApiError: If the role list cannot be fetched.
 */
export async function loadDevPresets(): Promise<DevRolePreset[]> {
  return deriveDevPresets(await listDevRoles());
}
