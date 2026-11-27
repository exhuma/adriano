/**
 * Business-object types for identity, permissions, and dev login,
 * derived from the generated OpenAPI schema (see
 * `scripts/gen-types.mjs`).
 */
import type { components } from "@/types/openapi";

/** A permission granted by the `rbac` section of `catalog.yaml`. */
export type Permission = components["schemas"]["Permission"];
/** Whether the caller may record approval decisions, and why. */
export type ReviewerOut = components["schemas"]["ReviewerOut"];
/** `GET /api/v1/me`: the authenticated caller and what they may do. */
export type MeOut = components["schemas"]["MeOut"];
/** `POST /auth/dev/login` request body. */
export type DevLoginIn = components["schemas"]["DevLoginIn"];
/** One `rbac` role of the loaded catalog (`GET /auth/dev/roles`). */
export type DevRoleOut = components["schemas"]["DevRoleOut"];
/** `GET /auth/dev/roles`: role names for dev sign-in presets. */
export type DevRolesOut = components["schemas"]["DevRolesOut"];
/** `POST /api/v1/sources/poll` and `/sources/{id}/poll` response. */
export type PollAcceptedOut = components["schemas"]["PollAcceptedOut"];
