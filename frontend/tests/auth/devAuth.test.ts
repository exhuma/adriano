/**
 * Ensure the dev-login flow mints a token through
 * `src/api/devAuth.ts` and reports the resulting session through
 * `src/composables/useAuth.ts`'s generic seam -- never the other way
 * around (see `src/auth/devAuth.ts`'s isolation docstring).
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const createDevToken = vi.fn();
const listDevRoles = vi.fn();
const setDevSession = vi.fn();
const clearDevSession = vi.fn();

vi.mock("@/api/devAuth", () => ({
  createDevToken: (...args: unknown[]) => createDevToken(...args),
  listDevRoles: () => listDevRoles(),
}));
vi.mock("@/composables/useAuth", () => ({
  setDevSession: (...args: unknown[]) => setDevSession(...args),
  clearDevSession: (...args: unknown[]) => clearDevSession(...args),
}));

describe("devAuth", () => {
  beforeEach(() => {
    createDevToken.mockReset();
    listDevRoles.mockReset();
    setDevSession.mockReset();
    clearDevSession.mockReset();
  });

  afterEach(() => {
    vi.resetModules();
  });

  it("mints a token and reports the session", async () => {
    createDevToken.mockResolvedValue({
      access_token: "dev-abc",
      token_type: "Bearer",
      expires_in: 3600,
    });
    const { devSignIn } = await import("@/auth/devAuth");

    await devSignIn({ sub: "alice", roles: ["admin"] });

    expect(createDevToken).toHaveBeenCalledWith({ sub: "alice", roles: ["admin"] });
    expect(setDevSession).toHaveBeenCalledWith("dev-abc");
  });

  it("propagates a minting failure without reporting a session", async () => {
    const failure = new Error("503");
    createDevToken.mockRejectedValue(failure);
    const { devSignIn } = await import("@/auth/devAuth");

    await expect(devSignIn({ sub: "alice", roles: [] })).rejects.toBe(failure);
    expect(setDevSession).not.toHaveBeenCalled();
  });

  it("devSignOut clears the session", async () => {
    const { devSignOut } = await import("@/auth/devAuth");
    devSignOut();
    expect(clearDevSession).toHaveBeenCalledOnce();
  });

  it("derives presets from the catalog's role names", async () => {
    listDevRoles.mockResolvedValue({
      roles: [
        { name: "admin", permissions: ["operate", "read"] },
        { name: "adr-reader", permissions: ["read"] },
      ],
      reviewer_roles: ["adr-reviewer"],
    });
    const { loadDevPresets } = await import("@/auth/devAuth");

    await expect(loadDevPresets()).resolves.toEqual([
      { label: "Reader", roles: ["adr-reader"] },
      { label: "Reviewer", roles: ["adr-reader", "adr-reviewer"] },
      { label: "Operator", roles: ["admin"] },
    ]);
  });

  it("propagates a role-list failure", async () => {
    const failure = new Error("404");
    listDevRoles.mockRejectedValue(failure);
    const { loadDevPresets } = await import("@/auth/devAuth");

    await expect(loadDevPresets()).rejects.toBe(failure);
  });
});
