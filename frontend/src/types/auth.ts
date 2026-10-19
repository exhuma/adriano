/**
 * Business-object types for identity, permissions, and dev tokens,
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
/** `POST /auth/dev/token` request body. */
export type DevTokenIn = components["schemas"]["DevTokenIn"];
/** `POST /auth/dev/token` response (OAuth2 token-response shape). */
export type DevTokenOut = components["schemas"]["DevTokenOut"];
/** `POST /api/v1/sources/poll` and `/sources/{id}/poll` response. */
export type PollAcceptedOut = components["schemas"]["PollAcceptedOut"];
