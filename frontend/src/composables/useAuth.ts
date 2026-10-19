/**
 * Singleton auth orchestration: wires the OIDC/dev-login token
 * sources into the API client's `TokenProvider`/401 seam, and
 * exposes sign-in/out actions for the app shell.
 *
 * Module-level state (no Pinia; `module-vue-vuetify` "State
 * management"). `initAuth()` is idempotent and called once from
 * `main.ts`.
 *
 * Deliberately has **no** dependency on `/auth/dev/token` or dev
 * token minting: that lives only in `src/auth/devAuth.ts`, reachable
 * only through the dynamically-imported `DevLoginDialog` (see
 * `App.vue`), so a production build's dead-code elimination can
 * remove the dev-login mechanism entirely (`module-dev-auth-bypass`).
 * `setDevSession`/`clearDevSession` below are the generic seam
 * `devAuth.ts` uses to report a dev sign-in/out; this module never
 * imports anything dev-specific.
 */
import { readonly, ref } from "vue";

import {
  setAuthSuccessHandler,
  setTokenProvider,
  setUnauthorizedHandler,
} from "@/api";
import { authError, handleUnauthorized, notifyAuthSuccess } from "@/auth/reauthGuard";
import { getUserManager, oidcConfigured } from "@/auth/oidc";
import { useMe } from "@/composables/useMe";

export type AuthMode = "oidc" | "dev" | null;

/** In-memory dev-login token (never `localStorage`/`sessionStorage`
 *  -- see `src/auth/oidc.ts` for why a page reload signing out is an
 *  accepted trade-off applied the same way to both auth modes). */
const devToken = ref<string | null>(null);
const authMode = ref<AuthMode>(null);
let initialized = false;

const meState = useMe();

async function currentToken(): Promise<string | null> {
  if (devToken.value) {
    return devToken.value;
  }
  const manager = getUserManager();
  if (!manager) {
    return null;
  }
  const user = await manager.getUser();
  return user && !user.expired ? user.access_token : null;
}

/**
 * Resolve a 401 by redirecting to the IdP, when one is configured
 * and this session is not a dev login. Otherwise there is no
 * redirect target: drop the session so the app falls back to the
 * sign-in screen (see `reauthGuard.ts` -- this carries no loop risk
 * because nothing retries automatically).
 *
 * :returns: Whether a redirect to the IdP was actually started.
 */
async function redirectToSignIn(): Promise<boolean> {
  const manager = getUserManager();
  if (devToken.value || !manager) {
    clearDevSession();
    return false;
  }
  await manager.signinRedirect({ state: window.location.pathname });
  return true;
}

/** Wire the API client's auth seam. Safe to call more than once;
 *  only the first call has any effect. */
export function initAuth(): void {
  if (initialized) {
    return;
  }
  initialized = true;
  setTokenProvider({ getToken: currentToken });
  setUnauthorizedHandler(() => handleUnauthorized({ redirectToSignIn }));
  setAuthSuccessHandler(notifyAuthSuccess);
}

/** Begin the OIDC Authorization Code + PKCE sign-in redirect. No-op
 *  when OIDC is not configured. */
export async function signInWithOidc(): Promise<void> {
  const manager = getUserManager();
  if (!manager) {
    return;
  }
  await manager.signinRedirect({ state: window.location.pathname });
}

/**
 * Complete the OIDC callback (`/auth/callback`) and load `/me`.
 *
 * :returns: The path to return to (the original path captured
 *     before the redirect), defaulting to `/`.
 * :throws Error: If OIDC is not configured, or the exchange fails
 *     (surfaced by the caller, `AuthCallbackView`).
 */
export async function completeOidcCallback(): Promise<string> {
  const manager = getUserManager();
  if (!manager) {
    throw new Error("OIDC is not configured");
  }
  const user = await manager.signinRedirectCallback();
  authMode.value = "oidc";
  await meState.load();
  const state = user.state;
  return typeof state === "string" && state.length > 0 ? state : "/";
}

/** Sign out of the active OIDC session (or dev login), clearing the
 *  cached identity. */
export async function signOut(): Promise<void> {
  if (devToken.value) {
    clearDevSession();
    return;
  }
  const manager = getUserManager();
  authMode.value = null;
  meState.clear();
  if (manager) {
    const user = await manager.getUser();
    if (user) {
      await manager.removeUser();
    }
  }
}

/**
 * Record a successful dev-login sign-in and load `/me`. Called by
 * `src/auth/devAuth.ts` after minting a token; this module never
 * mints the token itself.
 *
 * :param token: The minted dev access token.
 */
export async function setDevSession(token: string): Promise<void> {
  devToken.value = token;
  authMode.value = "dev";
  await meState.load();
}

/** Drop the dev-login token and cached identity. */
export function clearDevSession(): void {
  devToken.value = null;
  authMode.value = null;
  meState.clear();
}

/** Singleton auth state and actions for the app shell and views. */
export function useAuth() {
  return {
    me: meState.me,
    meLoading: meState.loading,
    meError: meState.error,
    can: meState.can,
    authMode: readonly(authMode),
    authError: readonly(authError),
    oidcConfigured,
    initAuth,
    signInWithOidc,
    completeOidcCallback,
    signOut,
  };
}
