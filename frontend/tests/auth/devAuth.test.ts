/**
 * Ensure the dev-login flow creates a session through
 * `src/api/devAuth.ts` and then reports it through
 * `src/composables/useAuth.ts`'s generic seam (which re-runs the
 * session check and loads `/me`) -- never the other way around (see
 * `src/auth/devAuth.ts`'s isolation docstring).
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const createDevSession = vi.fn();
const listDevRoles = vi.fn();
const setDevSession = vi.fn();

vi.mock("@/api/devAuth", () => ({
  createDevSession: (...args: unknown[]) => createDevSession(...args),
  listDevRoles: () => listDevRoles(),
}));
vi.mock("@/composables/useAuth", () => ({
  setDevSession: (...args: unknown[]) => setDevSession(...args),
}));

describe("devAuth", () => {
  beforeEach(() => {
    createDevSession.mockReset();
    listDevRoles.mockReset();
    setDevSession.mockReset();
  });

  afterEach(() => {
    vi.resetModules();
  });

  it("creates the dev session, then reports it", async () => {
    const order: string[] = [];
    createDevSession.mockImplementation(async () => {
      order.push("login");
    });
    setDevSession.mockImplementation(async () => {
      order.push("session");
    });
    const { devSignIn } = await import("@/auth/devAuth");

    await devSignIn({ sub: "alice", roles: ["admin"] });

    expect(createDevSession).toHaveBeenCalledWith({
      sub: "alice",
      roles: ["admin"],
    });
    expect(order).toEqual(["login", "session"]);
  });

  it("propagates a login failure without reporting a session", async () => {
    const failure = new Error("503");
    createDevSession.mockRejectedValue(failure);
    const { devSignIn } = await import("@/auth/devAuth");

    await expect(devSignIn({ sub: "alice", roles: [] })).rejects.toBe(failure);
    expect(setDevSession).not.toHaveBeenCalled();
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
