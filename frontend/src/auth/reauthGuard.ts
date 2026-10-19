/**
 * Re-authentication loop guard (`module-auth-oidc-vue`).
 *
 * A 401 usually means the session expired and one redirect to the
 * IdP fixes it. But a token can be cryptographically valid yet still
 * rejected by the resource server (wrong `aud`/`iss`, or a dev token
 * whose role mapping the backend does not recognise) -- in that case
 * re-authenticating returns the same rejected token, so an unguarded
 * "401 -> redirect" handler loops forever (worse with
 * `automaticSilentRenew`, which would silently refetch the same bad
 * token). This module bounds re-authentication to a single redirect
 * per failure episode and surfaces a blocking error instead of
 * looping a second time.
 *
 * The attempt counter lives in `sessionStorage` because it must
 * survive the full-page round trip to the IdP and back (an in-memory
 * variable would not -- the page is reloaded); it never holds a
 * token.
 */
import { ref } from "vue";

const ATTEMPT_KEY = "adriano.reauthAttempts";

/** Set (non-null) when re-authentication failed a second time in the
 *  same episode; the app shell renders this as a blocking dialog
 *  instead of redirecting again. `null` means no such failure is
 *  currently blocking the app. */
export const authError = ref<string | null>(null);

// Collapses the burst of parallel 401s one failed request wave can
// produce into a single redirect attempt.
let redirectInFlight = false;

function attempts(): number {
  return Number(sessionStorage.getItem(ATTEMPT_KEY) ?? "0");
}

/** How the guard resolves a 401, supplied by the caller so this
 *  module stays independent of which auth mode (OIDC or dev login)
 *  is active. */
export interface ReauthActions {
  /**
   * Attempt to resolve the rejection, returning whether a redirect
   * to the identity provider was actually initiated.
   *
   * :returns: `true` if a redirect was started (the page is about to
   *     navigate away); `false` when there is no redirect target
   *     (e.g. dev login, or no session at all) -- in which case the
   *     caller already dropped the rejected session.
   */
  redirectToSignIn: () => Promise<boolean>;
}

/**
 * Handle a 401 response from the API client.
 *
 * The first 401 in an episode tries one redirect to the identity
 * provider (if one is available). A second 401 without an
 * intervening success means re-authenticating did not help, so the
 * guard stops and surfaces `authError` instead of redirecting again.
 * When no redirect target exists at all (dev login, or already
 * signed out), there is no loop risk -- the caller already cleared
 * the session, so the app falls back to the sign-in screen.
 *
 * :param actions: Callbacks resolving the current auth mode.
 */
export function handleUnauthorized(actions: ReauthActions): void {
  if (redirectInFlight) {
    return;
  }
  if (attempts() >= 1) {
    sessionStorage.removeItem(ATTEMPT_KEY);
    authError.value =
      "Your session could not be authenticated, even after signing in " +
      "again. This usually means the token was rejected for a reason " +
      "sign-in cannot fix (for example a mismatched audience or " +
      "issuer). Sign out and try again, or contact an administrator.";
    return;
  }
  sessionStorage.setItem(ATTEMPT_KEY, String(attempts() + 1));
  redirectInFlight = true;
  void actions
    .redirectToSignIn()
    .then((redirected) => {
      if (!redirected) {
        // No redirect target: nothing will retry on its own, so
        // there is no loop to guard against.
        sessionStorage.removeItem(ATTEMPT_KEY);
      }
    })
    .finally(() => {
      redirectInFlight = false;
    });
}

/**
 * Clear the attempt counter and any blocking error after a request
 * succeeds, so a legitimate expiry-then-redirect-then-success cycle
 * never leaves a stale counter behind.
 */
export function notifyAuthSuccess(): void {
  sessionStorage.removeItem(ATTEMPT_KEY);
  authError.value = null;
}

/** Test-only reset of the module's internal in-flight flag. */
export function _resetReauthGuardForTests(): void {
  redirectInFlight = false;
  sessionStorage.removeItem(ATTEMPT_KEY);
  authError.value = null;
}
