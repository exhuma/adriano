/**
 * Dev sign-in role presets derived from the loaded catalog's role
 * names (`GET /auth/dev/roles`; docs/ui-review D-04).
 *
 * Pure functions only. Like `src/auth/devAuth.ts`, this module is
 * reachable only through the dynamically-imported `DevLoginDialog`,
 * so a production build drops it (`scripts/check-no-dev-auth.sh`).
 *
 * Rules (a preset the catalog cannot satisfy is left out):
 * - **Reader:** one role granting `read` but not `operate`, and not
 *   itself an approval-policy reviewer role.
 * - **Reviewer:** a reviewer role that already grants `read` on its
 *   own; otherwise a reviewer role combined with a read role.
 * - **Operator:** a role granting `operate` and `read`; otherwise an
 *   `operate` role combined with a read role.
 *
 * When several roles qualify, the read-only ones are preferred, then
 * the order the backend lists them in (sorted by name).
 */
import type { DevRoleOut, DevRolesOut, Permission } from "@/types/auth";

/** A one-click role preset for the dev sign-in dialog. */
export interface DevRolePreset {
  /** Button label: "Reader", "Reviewer" or "Operator". */
  label: string;
  /** Role names to put into the roles field, in order. */
  roles: string[];
}

function grants(role: DevRoleOut, permission: Permission): boolean {
  return role.permissions.includes(permission);
}

function isReadOnly(role: DevRoleOut): boolean {
  return grants(role, "read") && !grants(role, "operate");
}

function names(...roles: DevRoleOut[]): string[] {
  return roles.map((role) => role.name);
}

/**
 * Pick the best role that grants `read`: read-only non-reviewer
 * roles first, then other read-only roles, then any read role.
 */
function bestReadRole(
  roles: DevRoleOut[],
  reviewerRoles: Set<string>,
): DevRoleOut | undefined {
  return (
    roles.find((r) => isReadOnly(r) && !reviewerRoles.has(r.name)) ??
    roles.find(isReadOnly) ??
    roles.find((r) => grants(r, "read"))
  );
}

function readerPreset(
  roles: DevRoleOut[],
  reviewerRoles: Set<string>,
): string[] | null {
  const role = roles.find(
    (r) => isReadOnly(r) && !reviewerRoles.has(r.name),
  );
  return role ? names(role) : null;
}

function reviewerPreset(
  roles: DevRoleOut[],
  reviewerNames: string[],
): string[] | null {
  const byName = new Map(roles.map((role) => [role.name, role]));
  const reviewers = reviewerNames.map(
    (name) => byName.get(name) ?? { name, permissions: [] },
  );
  const selfRead =
    reviewers.find(isReadOnly) ?? reviewers.find((r) => grants(r, "read"));
  if (selfRead) {
    return names(selfRead);
  }
  const reviewer = reviewers[0];
  const read = bestReadRole(roles, new Set(reviewerNames));
  return reviewer && read ? names(read, reviewer) : null;
}

function operatorPreset(
  roles: DevRoleOut[],
  reviewerRoles: Set<string>,
): string[] | null {
  const full = roles.find((r) => grants(r, "operate") && grants(r, "read"));
  if (full) {
    return names(full);
  }
  const operate = roles.find((r) => grants(r, "operate"));
  const read = bestReadRole(roles, reviewerRoles);
  return operate && read ? names(read, operate) : null;
}

/**
 * Derive the dev sign-in presets from the catalog's role names.
 *
 * :param catalog: `GET /auth/dev/roles` response.
 * :returns: Reader, Reviewer and Operator presets, in that order,
 *     leaving out any the catalog cannot satisfy.
 */
export function deriveDevPresets(catalog: DevRolesOut): DevRolePreset[] {
  const reviewerRoles = new Set(catalog.reviewer_roles);
  const candidates: [string, string[] | null][] = [
    ["Reader", readerPreset(catalog.roles, reviewerRoles)],
    ["Reviewer", reviewerPreset(catalog.roles, catalog.reviewer_roles)],
    ["Operator", operatorPreset(catalog.roles, reviewerRoles)],
  ];
  return candidates.flatMap(([label, roles]) =>
    roles ? [{ label, roles }] : [],
  );
}
