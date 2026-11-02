/**
 * Ensure `useAuth` restores the session from the backend cookie on
 * startup, builds the sign-in URL with a safe `return_to`, resolves
 * 401s through the re-auth loop guard, and signs out by following the
 * IdP's end-session URL when there is one.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const apiGet = vi.fn();
const apiPost = vi.fn();
const setUnauthorizedHandler = vi.fn();
const setAuthSuccessHandler = vi.fn();
const getMe = vi.fn();
const assign = vi.fn();
const oidc = vi.hoisted(() => ({ enabled: true }));

// `useMe` (loaded transitively by `useAuth`) imports `ApiError` from
// "@/api" too, so the mock must still provide it.
class MockApiError extends Error {
  readonly status: number;
  readonly data: unknown;
  constructor(status: number, data: unknown) {
    super(`API request failed with status ${status}`);
    this.status = status;
    this.data = data;
  }
}

vi.mock("@/api", () => ({
  api: {
    get: (...args: unknown[]) => apiGet(...args),
    post: (...args: unknown[]) => apiPost(...args),
  },
  setUnauthorizedHandler: (...args: unknown[]) =>
    setUnauthorizedHandler(...args),
  setAuthSuccessHandler: (...args: unknown[]) =>
    setAuthSuccessHandler(...args),
  ApiError: MockApiError,
}));

vi.mock("@/config", () => ({
  get oidcEnabled() {
    return oidc.enabled;
  },
}));

vi.mock("@/api/auth", () => ({
  getMe: (...args: unknown[]) => getMe(...args),
}));

const alice = {
  issuer: "adriano-dev",
  subject: "alice",
  display: "Alice",
  email: null,
  roles: ["admin"],
  permissions: ["read", "operate"],
  reviewer: { eligible: false, reason: "n/a" },
};

/** Resolve `GET /auth/session` with the given authenticated flag. */
function sessionIs(authenticated: boolean): void {
  apiGet.mockImplementation(async (path: string) => {
    if (path === "/auth/session") {
      return { authenticated };
    }
    throw new Error(`unexpected GET ${path}`);
  });
}

async function loadAuth() {
  return import("@/composables/useAuth");
}

describe("useAuth", () => {
  const originalLocation = window.location;

  beforeEach(() => {
    vi.resetModules();
    apiGet.mockReset();
    apiPost.mockReset();
    setUnauthorizedHandler.mockReset();
    setAuthSuccessHandler.mockReset();
    getMe.mockReset().mockResolvedValue(alice);
    assign.mockReset();
    oidc.enabled = true;
    sessionStorage.clear();
    Object.defineProperty(window, "location", {
      configurable: true,
      value: { pathname: "/records/42", search: "?tab=diff", assign },
    });
  });

  afterEach(() => {
    Object.defineProperty(window, "location", {
      configurable: true,
      value: originalLocation,
    });
    vi.restoreAllMocks();
  });

  describe("startup session restore", () => {
    it("loads the identity when the backend reports a session", async () => {
      sessionIs(true);
      const { initAuth, useAuth } = await loadAuth();
      const auth = useAuth();

      expect(auth.sessionChecked.value).toBe(false);
      initAuth();
      await vi.waitFor(() => expect(auth.sessionChecked.value).toBe(true));

      expect(apiGet).toHaveBeenCalledWith("/auth/session", {
        trackAuth: false,
      });
      expect(getMe).toHaveBeenCalledOnce();
      expect(auth.me.value?.display).toBe("Alice");
      expect(auth.authMode.value).toBe("oidc");
    });

    it("stays signed out without loading /me when there is no session", async () => {
      sessionIs(false);
      const { initAuth, useAuth } = await loadAuth();
      const auth = useAuth();

      initAuth();
      await vi.waitFor(() => expect(auth.sessionChecked.value).toBe(true));

      expect(getMe).not.toHaveBeenCalled();
      expect(auth.me.value).toBeNull();
      expect(auth.authMode.value).toBeNull();
    });

    it("treats a failed session check as signed out and finishes checking", async () => {
      apiGet.mockRejectedValue(new Error("network down"));
      const { initAuth, useAuth } = await loadAuth();
      const auth = useAuth();

      initAuth();
      await vi.waitFor(() => expect(auth.sessionChecked.value).toBe(true));

      expect(auth.me.value).toBeNull();
    });

    it("keeps reporting 'checking' while the request is pending", async () => {
      apiGet.mockReturnValue(new Promise(() => {}));
      const { initAuth, useAuth } = await loadAuth();
      const auth = useAuth();

      initAuth();
      await Promise.resolve();

      expect(auth.sessionChecked.value).toBe(false);
    });

    it("initAuth is idempotent: a second call neither re-registers nor re-checks", async () => {
      sessionIs(false);
      const { initAuth } = await loadAuth();
      initAuth();
      initAuth();

      expect(setUnauthorizedHandler).toHaveBeenCalledOnce();
      expect(setAuthSuccessHandler).toHaveBeenCalledOnce();
      expect(apiGet).toHaveBeenCalledOnce();
    });
  });

  describe("sign-in", () => {
    it("navigates to /auth/login with the current path as return_to", async () => {
      const { signInWithOidc } = await loadAuth();

      signInWithOidc();

      expect(assign).toHaveBeenCalledWith(
        `/auth/login?return_to=${encodeURIComponent("/records/42?tab=diff")}`,
      );
    });

    it("does nothing when OIDC is not available", async () => {
      oidc.enabled = false;
      const { signInWithOidc } = await loadAuth();

      signInWithOidc();

      expect(assign).not.toHaveBeenCalled();
    });
  });

  describe("401 handling", () => {
    async function unauthorized(): Promise<void> {
      sessionIs(false);
      const { initAuth } = await loadAuth();
      initAuth();
      const handler = setUnauthorizedHandler.mock.calls[0]?.[0] as () => void;
      handler();
      await new Promise((resolve) => setTimeout(resolve, 0));
    }

    it("redirects to the sign-in once, with the return path", async () => {
      await unauthorized();

      expect(assign).toHaveBeenCalledOnce();
      expect(assign.mock.calls[0]?.[0]).toContain("/auth/login?return_to=");
    });

    it("stops redirecting after one failed attempt and surfaces a blocking error", async () => {
      const guard = await import("@/auth/reauthGuard");
      guard._resetReauthGuardForTests();
      await unauthorized();
      const handler = setUnauthorizedHandler.mock.calls[0]?.[0] as () => void;
      // Let the first redirect settle, then a second 401 arrives
      // without any intervening success.
      await new Promise((resolve) => setTimeout(resolve, 0));
      handler();

      expect(assign).toHaveBeenCalledOnce();
      expect(guard.authError.value).not.toBeNull();
    });

    it("falls back to the sign-in screen when OIDC is not available", async () => {
      oidc.enabled = false;
      const guard = await import("@/auth/reauthGuard");
      guard._resetReauthGuardForTests();
      await unauthorized();

      expect(assign).not.toHaveBeenCalled();
    });
  });

  describe("sign-out", () => {
    it("posts the logout, clears the identity and follows end_session_url", async () => {
      sessionIs(true);
      apiPost.mockResolvedValue({ end_session_url: "https://idp/logout?x=1" });
      const { initAuth, signOut, useAuth } = await loadAuth();
      const auth = useAuth();
      initAuth();
      await vi.waitFor(() => expect(auth.me.value).not.toBeNull());

      await signOut();

      expect(apiPost).toHaveBeenCalledWith("/auth/logout", undefined, {
        trackAuth: false,
      });
      expect(auth.me.value).toBeNull();
      expect(assign).toHaveBeenCalledWith("https://idp/logout?x=1");
    });

    it("stays on the app (sign-in screen) when end_session_url is null", async () => {
      sessionIs(true);
      apiPost.mockResolvedValue({ end_session_url: null });
      const { initAuth, signOut, useAuth } = await loadAuth();
      const auth = useAuth();
      initAuth();
      await vi.waitFor(() => expect(auth.me.value).not.toBeNull());

      await signOut();

      expect(auth.me.value).toBeNull();
      expect(assign).not.toHaveBeenCalled();
    });

    it("still leaves the signed-in state when the logout request fails", async () => {
      sessionIs(true);
      apiPost.mockRejectedValue(new Error("network down"));
      const { initAuth, signOut, useAuth } = await loadAuth();
      const auth = useAuth();
      initAuth();
      await vi.waitFor(() => expect(auth.me.value).not.toBeNull());

      await signOut();

      expect(auth.me.value).toBeNull();
      expect(assign).not.toHaveBeenCalled();
    });
  });

  describe("dev session", () => {
    it("setDevSession re-runs the session check, loads /me and marks the mode", async () => {
      sessionIs(true);
      const { setDevSession, useAuth } = await loadAuth();
      const auth = useAuth();

      await setDevSession();

      expect(apiGet).toHaveBeenCalledWith("/auth/session", {
        trackAuth: false,
      });
      expect(auth.me.value?.display).toBe("Alice");
      expect(auth.authMode.value).toBe("dev");
    });

    it("remembers the dev mode across a reload", async () => {
      sessionIs(true);
      const first = await loadAuth();
      await first.setDevSession();
      vi.resetModules();

      const second = await loadAuth();
      second.initAuth();
      await vi.waitFor(() =>
        expect(second.useAuth().sessionChecked.value).toBe(true),
      );

      expect(second.useAuth().authMode.value).toBe("dev");
    });

    it("signs out of a dev session through the regular logout", async () => {
      sessionIs(true);
      apiPost.mockResolvedValue({ end_session_url: null });
      const { setDevSession, signOut, useAuth } = await loadAuth();
      await setDevSession();

      await signOut();

      expect(apiPost).toHaveBeenCalledWith("/auth/logout", undefined, {
        trackAuth: false,
      });
      expect(useAuth().authMode.value).toBeNull();
    });
  });
});
