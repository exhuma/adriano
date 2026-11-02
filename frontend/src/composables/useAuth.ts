/**
 * Singleton auth orchestration for the Backend-for-Frontend session:
 * restores the session on startup, wires the API client's 401/success
 * seams into the re-auth loop guard, and exposes sign-in/out actions
 * for the app shell.
 *
 * The browser holds no tokens. The backend keeps them in a
 * server-side session and hands the browser an HttpOnly cookie, so
 * "am I signed in?" is answered by `GET /auth/session` -- on every
 * page load, which is what lets a reload keep the user signed in.
 *
 * Module-level state (no Pinia; `module-vue-vuetify` "State
 * management"). `initAuth()` is idempotent and called once from
 * `main.ts`.
 *
 * Deliberately has **no** dependency on `/auth/dev/login` or any
 * other dev-login code: that lives only in `src/auth/devAuth.ts`,
 * reachable only through the dynamically-imported `DevLoginDialog`
 * (see `App.vue`), so a production build's dead-code elimination
 * can remove the dev-login mechanism entirely
 * (`module-dev-auth-bypass`). `setDevSession` below is the generic
 * seam `devAuth.ts` uses to report a dev sign-in; this module never
 * imports anything dev-specific.
 */
import { computed, readonly, ref } from "vue";

import {
  api,
  setAuthSuccessHandler,
  setUnauthorizedHandler,
} from "@/api";
import {
  authError,
  handleUnauthorized,
  notifyAuthSuccess,
} from "@/auth/reauthGuard";
import { oidcEnabled } from "@/config";
import { useMe } from "@/composables/useMe";

export type AuthMode = "oidc" | "dev" | null;

/** `GET /auth/session` response. */
interface SessionStatus {
  authenticated: boolean;
  expires_at?: string | null;
}

/** `POST /auth/logout` response. */
interface LogoutResult {
  end_session_url: string | null;
}

/** `sessionStorage` key remembering that the current session is a
 *  dev login, so the DEV LOGIN mode indicator survives a reload.
 *  Holds a flag only, never any credential. */
const DEV_SESSION_KEY = "adriano.devSession";

const meState = useMe();

/** `true` once the startup session check has finished, whatever its
 *  outcome; the shell shows a neutral loading state until then so the
 *  sign-in screen never flashes for a user who is signed in. */
const sessionChecked = ref(false);
const devSession = ref(readDevFlag());
let initialized = false;

/** Which kind of session is active, for the mode indicator. */
const authMode = computed<AuthMode>(() => {
  if (meState.me.value === null) {
    return null;
  }
  return devSession.value ? "dev" : "oidc";
});

function readDevFlag(): boolean {
  try {
    return sessionStorage.getItem(DEV_SESSION_KEY) === "1";
  } catch {
    return false;
  }
}

function writeDevFlag(value: boolean): void {
  devSession.value = value;
  try {
    if (value) {
      sessionStorage.setItem(DEV_SESSION_KEY, "1");
    } else {
      sessionStorage.removeItem(DEV_SESSION_KEY);
    }
  } catch {
    // The indicator then only lasts until the next reload.
  }
}

/** Drop the cached identity and the dev flag. */
function dropIdentity(): void {
  writeDevFlag(false);
  meState.clear();
}

/** Drop the local view of the session entirely: identity, dev flag,
 *  and any blocking sign-in error with its re-auth counter. */
function clearLocalSession(): void {
  dropIdentity();
  notifyAuthSuccess();
}

/**
 * Ask the backend whether the browser has a session and, if so, load
 * the caller's identity. Never throws: a failed check leaves the user
 * signed out, which shows the sign-in screen.
 *
 * Does not take part in the re-auth loop guard (`trackAuth: false`):
 * a valid session says nothing about whether the API accepts it.
 */
export async function restoreSession(): Promise<void> {
  try {
    const status = await api.get<SessionStatus>("/auth/session", {
      trackAuth: false,
    });
    if (status.authenticated) {
      await meState.load();
    } else {
      dropIdentity();
    }
  } catch {
    dropIdentity();
  } finally {
    sessionChecked.value = true;
  }
}

/**
 * Build the backend sign-in URL for the page the user is on.
 *
 * :returns: ``/auth/login?return_to=<current path and query>``.
 */
function loginUrl(): string {
  const here = window.location.pathname + window.location.search;
  return `/auth/login?return_to=${encodeURIComponent(here)}`;
}

/**
 * Resolve a 401 by sending the browser to the backend sign-in, when
 * OIDC is available and this is not a dev session. Otherwise there is
 * no redirect target: drop the session so the app falls back to the
 * sign-in screen (see `reauthGuard.ts` -- this carries no loop risk
 * because nothing retries automatically).
 *
 * :returns: Whether a redirect to the sign-in was actually started.
 */
async function redirectToSignIn(): Promise<boolean> {
  if (!oidcEnabled || devSession.value) {
    clearLocalSession();
    return false;
  }
  window.location.assign(loginUrl());
  return true;
}

/** Wire the API client's auth seams and start the startup session
 *  check. Safe to call more than once; only the first call has any
 *  effect. */
export function initAuth(): void {
  if (initialized) {
    return;
  }
  initialized = true;
  setUnauthorizedHandler(() => handleUnauthorized({ redirectToSignIn }));
  setAuthSuccessHandler(notifyAuthSuccess);
  void restoreSession();
}

/** Begin the OIDC sign-in: a full-page navigation to the backend,
 *  which redirects to the IdP and returns to the current page. No-op
 *  when OIDC is not available. */
export function signInWithOidc(): void {
  if (!oidcEnabled) {
    return;
  }
  window.location.assign(loginUrl());
}

/**
 * Sign out: end the server-side session, drop the cached identity,
 * and follow the IdP's end-session URL if the backend returned one.
 * Otherwise the sign-in screen appears.
 *
 * The local state is cleared even if the request fails (the server
 * ends the session by expiry regardless), so the UI never claims a
 * signed-in state the user just asked to leave.
 */
export async function signOut(): Promise<void> {
  let endSessionUrl: string | null = null;
  try {
    const result = await api.post<LogoutResult>("/auth/logout", undefined, {
      trackAuth: false,
    });
    endSessionUrl = result?.end_session_url ?? null;
  } catch {
    // Fall through: still leave the signed-in UI.
  }
  clearLocalSession();
  if (endSessionUrl) {
    window.location.assign(endSessionUrl);
  }
}

/**
 * Record a successful dev login: the backend has set the session
 * cookie, so re-run the session check and load `/me`. Called by
 * `src/auth/devAuth.ts`; this module never performs the dev login
 * itself.
 */
export async function setDevSession(): Promise<void> {
  writeDevFlag(true);
  await restoreSession();
}

/** Singleton auth state and actions for the app shell and views. */
export function useAuth() {
  return {
    me: meState.me,
    meLoading: meState.loading,
    meError: meState.error,
    can: meState.can,
    authMode,
    authError: readonly(authError),
    sessionChecked: readonly(sessionChecked),
    oidcEnabled,
    initAuth,
    signInWithOidc,
    signOut,
  };
}
