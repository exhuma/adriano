/**
 * Typed calls to the identity endpoint. The dev-only token endpoint
 * lives separately in `src/api/devAuth.ts`, which this module never
 * imports (see that file's docstring).
 */
import { api } from "@/api";
import type { MeOut } from "@/types/auth";

export type { MeOut };

/**
 * Describe the authenticated caller: identity, permissions, and
 * reviewer eligibility.
 *
 * :returns: The `/api/v1/me` payload.
 * :throws ApiError: `401` if unauthenticated, `503` if the backend
 *     cannot authenticate anyone (auth not configured/unavailable).
 */
export function getMe(): Promise<MeOut> {
  return api.get<MeOut>("/api/v1/me");
}
