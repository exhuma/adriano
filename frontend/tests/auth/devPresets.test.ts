/**
 * Ensure dev sign-in presets are derived from the catalog's role
 * names: Reader is read-only, Reviewer adds a
 * read role to a reviewer role unless that role already reads,
 * Operator needs `operate` (preferring a role that is not a reviewer
 * role), and unsatisfiable presets are left out.
 */
import { describe, expect, it } from "vitest";

import { deriveDevPresets } from "@/auth/devPresets";
import type { DevRolesOut } from "@/types/auth";

/** The repository's local `catalog.yaml`. */
const LOCAL: DevRolesOut = {
  roles: [
    { name: "admin", permissions: ["operate", "read"] },
    { name: "adr-reader", permissions: ["read"] },
  ],
  reviewer_roles: ["adr-reviewer"],
};

/** `catalog.demo.yaml`. */
const DEMO: DevRolesOut = {
  roles: [
    { name: "admin", permissions: ["operate", "read"] },
    { name: "adr-reviewer", permissions: ["read"] },
    { name: "reader", permissions: ["read"] },
  ],
  reviewer_roles: ["adr-reviewer"],
};

describe("deriveDevPresets", () => {
  it("combines a read role with a reviewer role that grants nothing", () => {
    expect(deriveDevPresets(LOCAL)).toEqual([
      { label: "Reader", roles: ["adr-reader"] },
      { label: "Reviewer", roles: ["adr-reader", "adr-reviewer"] },
      { label: "Operator", roles: ["admin"] },
    ]);
  });

  it("uses a reviewer role alone when it already grants read", () => {
    expect(deriveDevPresets(DEMO)).toEqual([
      { label: "Reader", roles: ["reader"] },
      { label: "Reviewer", roles: ["adr-reviewer"] },
      { label: "Operator", roles: ["admin"] },
    ]);
  });

  it("never offers a reviewer role as the Reader preset", () => {
    const presets = deriveDevPresets({
      roles: [
        { name: "admin", permissions: ["operate", "read"] },
        { name: "adr-reviewer", permissions: ["read"] },
      ],
      reviewer_roles: ["adr-reviewer"],
    });

    expect(presets.map((preset) => preset.label)).toEqual([
      "Reviewer",
      "Operator",
    ]);
  });

  it("hides Reviewer when there are no reviewer roles", () => {
    const presets = deriveDevPresets({ ...LOCAL, reviewer_roles: [] });

    expect(presets.map((preset) => preset.label)).toEqual([
      "Reader",
      "Operator",
    ]);
  });

  it("hides Operator when no role grants operate", () => {
    const presets = deriveDevPresets({
      roles: [{ name: "adr-reader", permissions: ["read"] }],
      reviewer_roles: ["adr-reviewer"],
    });

    expect(presets).toEqual([
      { label: "Reader", roles: ["adr-reader"] },
      { label: "Reviewer", roles: ["adr-reader", "adr-reviewer"] },
    ]);
  });

  it("combines an operate-only role with a read role", () => {
    const presets = deriveDevPresets({
      roles: [
        { name: "adr-reader", permissions: ["read"] },
        { name: "poller", permissions: ["operate"] },
      ],
      reviewer_roles: [],
    });

    expect(presets).toContainEqual({
      label: "Operator",
      roles: ["adr-reader", "poller"],
    });
  });

  it("uses an operator role for Reviewer when it is the only reader", () => {
    const presets = deriveDevPresets({
      roles: [{ name: "admin", permissions: ["operate", "read"] }],
      reviewer_roles: ["adr-reviewer"],
    });

    expect(presets).toEqual([
      { label: "Reviewer", roles: ["admin", "adr-reviewer"] },
      { label: "Operator", roles: ["admin"] },
    ]);
  });

  it("prefers an operate role that is not a reviewer role, so " +
    "Operator cannot also decide", () => {
    const presets = deriveDevPresets({
      roles: [
        { name: "adr-reader", permissions: ["read"] },
        { name: "lead", permissions: ["operate", "read"] },
        { name: "ops", permissions: ["operate", "read"] },
      ],
      reviewer_roles: ["lead"],
    });

    expect(presets).toContainEqual({ label: "Operator", roles: ["ops"] });
  });

  it("prefers a non-reviewer operate-only role over a reviewer role " +
    "granting operate and read", () => {
    const presets = deriveDevPresets({
      roles: [
        { name: "adr-reader", permissions: ["read"] },
        { name: "lead", permissions: ["operate", "read"] },
        { name: "poller", permissions: ["operate"] },
      ],
      reviewer_roles: ["lead"],
    });

    expect(presets).toContainEqual({
      label: "Operator",
      roles: ["adr-reader", "poller"],
    });
  });

  it("falls back to a reviewer role when it alone grants operate", () => {
    const presets = deriveDevPresets({
      roles: [
        { name: "adr-reader", permissions: ["read"] },
        { name: "lead", permissions: ["operate", "read"] },
      ],
      reviewer_roles: ["lead"],
    });

    expect(presets).toContainEqual({ label: "Operator", roles: ["lead"] });
  });

  it("offers nothing for a catalog without roles", () => {
    expect(deriveDevPresets({ roles: [], reviewer_roles: [] })).toEqual([]);
    expect(
      deriveDevPresets({ roles: [], reviewer_roles: ["adr-reviewer"] }),
    ).toEqual([]);
  });
});
