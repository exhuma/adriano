/**
 * Ensure the re-authentication loop guard redirects exactly once per
 * failure episode, stops and surfaces a blocking error on a second
 * 401 without an intervening success, and resets cleanly after a
 * success (`module-auth-oidc-vue` "Re-authentication loop guard").
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  _resetReauthGuardForTests,
  authError,
  handleUnauthorized,
  notifyAuthSuccess,
} from "@/auth/reauthGuard";

/** Let every pending microtask (including `.then()`/`.finally()`
 *  chains inside `handleUnauthorized`) settle before the next
 *  assertion or call -- a plain `await Promise.resolve()` only
 *  advances one microtask hop, which is not enough to observe
 *  `redirectInFlight` flip back to `false`. */
function flush(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

describe("reauthGuard", () => {
  beforeEach(() => {
    _resetReauthGuardForTests();
    sessionStorage.clear();
  });

  it("redirects exactly once on the first 401 of an episode", async () => {
    const redirectToSignIn = vi.fn().mockResolvedValue(true);

    handleUnauthorized({ redirectToSignIn });
    await flush();

    expect(redirectToSignIn).toHaveBeenCalledOnce();
    expect(authError.value).toBeNull();
  });

  it("does not redirect again and surfaces a blocking error on a second 401", async () => {
    const redirectToSignIn = vi.fn().mockResolvedValue(true);

    handleUnauthorized({ redirectToSignIn });
    await flush();
    expect(redirectToSignIn).toHaveBeenCalledOnce();

    handleUnauthorized({ redirectToSignIn });
    await flush();

    expect(redirectToSignIn).toHaveBeenCalledOnce();
    expect(authError.value).not.toBeNull();
    expect(authError.value).toContain("Sign out");
  });

  it("resets the attempt counter and any blocking error on success", async () => {
    const redirectToSignIn = vi.fn().mockResolvedValue(true);
    handleUnauthorized({ redirectToSignIn });
    await flush();
    handleUnauthorized({ redirectToSignIn });
    await flush();
    expect(authError.value).not.toBeNull();

    notifyAuthSuccess();

    expect(authError.value).toBeNull();
    expect(sessionStorage.getItem("adriano.reauthAttempts")).toBeNull();

    // A fresh episode after a success gets its own single redirect.
    redirectToSignIn.mockClear();
    handleUnauthorized({ redirectToSignIn });
    await flush();
    expect(redirectToSignIn).toHaveBeenCalledOnce();
  });

  it("does not loop when there is no redirect target (dev login/signed out)", async () => {
    const redirectToSignIn = vi.fn().mockResolvedValue(false);

    handleUnauthorized({ redirectToSignIn });
    await flush();

    expect(redirectToSignIn).toHaveBeenCalledOnce();
    expect(authError.value).toBeNull();
    expect(sessionStorage.getItem("adriano.reauthAttempts")).toBeNull();

    // No loop risk: a further 401 tries again rather than blocking.
    handleUnauthorized({ redirectToSignIn });
    await flush();
    expect(redirectToSignIn).toHaveBeenCalledTimes(2);
    expect(authError.value).toBeNull();
  });
});
