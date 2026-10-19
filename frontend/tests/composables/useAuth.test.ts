/**
 * Ensure `useAuth`/`initAuth` wire the API client's TokenProvider
 * seam correctly: a dev-login token (when set via `setDevSession`)
 * wins, otherwise the mocked OIDC `UserManager`'s unexpired user
 * supplies the token, and a missing/expired user yields `null` so no
 * `Authorization` header is sent.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

interface TokenProvider {
  getToken(): string | null | Promise<string | null>;
}

const setTokenProvider = vi.fn();
const setUnauthorizedHandler = vi.fn();
const setAuthSuccessHandler = vi.fn();
const getUser = vi.fn();

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
  setTokenProvider: (...args: unknown[]) => setTokenProvider(...args),
  setUnauthorizedHandler: (...args: unknown[]) => setUnauthorizedHandler(...args),
  setAuthSuccessHandler: (...args: unknown[]) => setAuthSuccessHandler(...args),
  ApiError: MockApiError,
}));

vi.mock("@/auth/oidc", () => ({
  getUserManager: () => ({
    getUser,
    signinRedirect: vi.fn(),
    signinRedirectCallback: vi.fn(),
    removeUser: vi.fn(),
  }),
  oidcConfigured: true,
}));

vi.mock("@/api/auth", () => ({
  getMe: vi.fn().mockResolvedValue({
    issuer: "adriano-dev",
    subject: "alice",
    display: "Alice",
    email: null,
    roles: ["admin"],
    permissions: ["read", "operate"],
    reviewer: { eligible: false, reason: "n/a" },
  }),
}));

function capturedProvider(): TokenProvider {
  const call = setTokenProvider.mock.calls.at(-1);
  if (!call) {
    throw new Error("setTokenProvider was never called");
  }
  return call[0] as TokenProvider;
}

describe("useAuth token provider wiring", () => {
  beforeEach(() => {
    vi.resetModules();
    setTokenProvider.mockClear();
    setUnauthorizedHandler.mockClear();
    setAuthSuccessHandler.mockClear();
    getUser.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns null when no dev token and no OIDC user is present", async () => {
    getUser.mockResolvedValue(null);
    const { initAuth } = await import("@/composables/useAuth");
    initAuth();

    expect(setTokenProvider).toHaveBeenCalledOnce();
    await expect(capturedProvider().getToken()).resolves.toBeNull();
  });

  it("returns the OIDC access token when the user is present and unexpired", async () => {
    getUser.mockResolvedValue({ expired: false, access_token: "oidc-token" });
    const { initAuth } = await import("@/composables/useAuth");
    initAuth();

    await expect(capturedProvider().getToken()).resolves.toBe("oidc-token");
  });

  it("returns null for an expired OIDC user", async () => {
    getUser.mockResolvedValue({ expired: true, access_token: "stale-token" });
    const { initAuth } = await import("@/composables/useAuth");
    initAuth();

    await expect(capturedProvider().getToken()).resolves.toBeNull();
  });

  it("prefers a dev-login token over any OIDC user", async () => {
    getUser.mockResolvedValue({ expired: false, access_token: "oidc-token" });
    const { initAuth, setDevSession } = await import("@/composables/useAuth");
    initAuth();
    await setDevSession("dev-token");

    await expect(capturedProvider().getToken()).resolves.toBe("dev-token");
  });

  it("clearDevSession drops the dev token so the provider falls through to OIDC", async () => {
    getUser.mockResolvedValue({ expired: false, access_token: "oidc-token" });
    const { initAuth, setDevSession, clearDevSession } = await import(
      "@/composables/useAuth"
    );
    initAuth();
    await setDevSession("dev-token");
    clearDevSession();

    await expect(capturedProvider().getToken()).resolves.toBe("oidc-token");
  });

  it("initAuth is idempotent: a second call does not re-register", async () => {
    getUser.mockResolvedValue(null);
    const { initAuth } = await import("@/composables/useAuth");
    initAuth();
    const callsBefore = setTokenProvider.mock.calls.length;
    initAuth();

    expect(setTokenProvider.mock.calls.length).toBe(callsBefore);
  });
});
