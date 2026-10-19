/**
 * Singleton composable for `GET /api/v1/me`: the authenticated
 * caller's identity, permissions, and reviewer eligibility.
 *
 * Module-level state (no Pinia; `module-vue-vuetify` "State
 * management") so every component sees the same identity without
 * re-fetching, and `useAuth` can call `load`/`clear` from its
 * sign-in/sign-out flows.
 */
import { readonly, ref } from "vue";

import { ApiError } from "@/api";
import { getMe } from "@/api/auth";
import type { MeOut, Permission } from "@/types/auth";
import { errorDetail } from "@/utils/apiErrors";

/** Why `/api/v1/me` could not be loaded, for a tailored message. */
export type MeErrorKind = "forbidden" | "unavailable" | "unknown";

/** A failure to load the caller's identity. */
export interface MeError {
  /** Category driving which message/recovery UI to show. */
  kind: MeErrorKind;
  /** Server-provided detail, when available. */
  detail: string;
}

const me = ref<MeOut | null>(null);
const loading = ref(false);
const error = ref<MeError | null>(null);

/** Singleton `/api/v1/me` state and loader, plus permission checks. */
export function useMe() {
  /**
   * Fetch and cache the caller's identity. Call after a sign-in
   * (OIDC or dev) and whenever a check against the policy is
   * needed; a 401 is left to the global re-auth guard (see
   * `src/auth/reauthGuard.ts`), so it clears `me` without setting
   * `error`.
   */
  async function load(): Promise<void> {
    loading.value = true;
    error.value = null;
    try {
      me.value = await getMe();
    } catch (err) {
      me.value = null;
      if (err instanceof ApiError) {
        if (err.status === 403) {
          error.value = {
            kind: "forbidden",
            detail:
              errorDetail(err) ??
              "You don't have permission to browse the catalog.",
          };
        } else if (err.status === 503) {
          error.value = {
            kind: "unavailable",
            detail:
              errorDetail(err) ??
              "The backend cannot authenticate anyone right now.",
          };
        } else if (err.status !== 401) {
          error.value = {
            kind: "unknown",
            detail: errorDetail(err) ?? "Could not load your account.",
          };
        }
        // 401: the unauthorized handler already took over (redirect
        // or blocking error); leave `error` unset so this composable
        // does not show a second, redundant message.
      } else {
        error.value = { kind: "unknown", detail: "Could not load your account." };
      }
    } finally {
      loading.value = false;
    }
  }

  /** Drop the cached identity (on sign-out). */
  function clear(): void {
    me.value = null;
    error.value = null;
  }

  /**
   * Whether the signed-in caller holds *permission*.
   *
   * :param permission: Permission to check (`"read"` or
   *     `"operate"`).
   * :returns: `true` if granted.
   */
  function can(permission: Permission): boolean {
    return me.value?.permissions.includes(permission) ?? false;
  }

  return {
    me: readonly(me),
    loading: readonly(loading),
    error: readonly(error),
    load,
    clear,
    can,
  };
}
