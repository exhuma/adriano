/**
 * Typed call to the decision endpoint. Every reviewer action goes
 * through the shared `api` client (see `@/api`), which owns
 * authentication headers and error shaping; this module only builds
 * the path and body.
 */
import { api } from "@/api";
import type { DecisionIn, DecisionSummaryOut } from "@/types/approval";

export type { DecisionIn, DecisionSummaryOut };

/**
 * Record an accept/reject decision for a record's current content.
 *
 * Always send `expected_digest` (the digest the reviewer last saw):
 * the server answers 409 `digest_changed` when the content moved on
 * since, instead of silently deciding content nobody reviewed.
 *
 * :param adrUuid: The ADR's UUID.
 * :param body: The action, optional comment, and expected digest.
 * :param ref: A candidate's ref; omitted to decide the published
 *     row.
 * :returns: The stored decision event.
 * :throws ApiError: 409 (`digest_changed`, `already_decided`,
 *     `policy_missing`, `approval_not_required`, `not_approvable`),
 *     403 (`not_eligible`, `self_approval`), or 404
 *     (`record_not_found`).
 */
export function postDecision(
  adrUuid: string,
  body: DecisionIn,
  ref?: string,
): Promise<DecisionSummaryOut> {
  const query = ref === undefined ? "" : `?ref=${encodeURIComponent(ref)}`;
  return api.post<DecisionSummaryOut>(
    `/api/v1/records/${encodeURIComponent(adrUuid)}/decisions${query}`,
    body,
  );
}
