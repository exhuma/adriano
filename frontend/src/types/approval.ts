/**
 * Business-object types for the approval workflow (decisions, policy,
 * divergence, diff), derived from the generated OpenAPI schema in
 * `openapi.ts` (see `scripts/gen-types.mjs`). Record-level approval
 * types that already live in `records.ts` (the detail payload's
 * `approval` field and its neighbours) are re-exported here so every
 * approval-related import can come from this one module; the new
 * types this phase adds are declared directly below.
 */
import type { components } from "@/types/openapi";
import type {
  ApprovalOut,
  ApprovalStateCode,
  DecisionAction,
  DecisionSummaryOut,
  PolicyStatus,
  PolicySummaryOut,
} from "@/types/records";

export type {
  ApprovalOut,
  ApprovalStateCode,
  DecisionAction,
  DecisionSummaryOut,
  PolicyStatus,
  PolicySummaryOut,
};

/** The decided row as it was at decision time. */
export type DecisionProvenanceOut =
  components["schemas"]["DecisionProvenanceOut"];
/** Kinds of published/accepted divergence within one identity. */
export type DivergenceKind = components["schemas"]["DivergenceKind"];
/** Content divergence within the record's identity. */
export type DivergenceOut = components["schemas"]["DivergenceOut"];
/** Another candidate of the identity with different content. */
export type CompetingCandidateOut =
  components["schemas"]["CompetingCandidateOut"];
/** Body of `POST /api/v1/records/{id}/decisions`. */
export type DecisionIn = components["schemas"]["DecisionIn"];
/** Outcome of `PUT`/`POST /api/v1/candidates`. */
export type CandidateResultOut = components["schemas"]["CandidateResultOut"];
/** One side of a diff (base or target). */
export type DiffEndpointOut = components["schemas"]["DiffEndpointOut"];
/** A unified diff between two stored content snapshots. */
export type RecordDiffOut = components["schemas"]["RecordDiffOut"];

/**
 * Stable machine-readable reason the caller cannot decide now, from
 * `approval.decide_blocked_code` on the record detail.
 */
export type DecideBlockedCode =
  | "policy_missing"
  | "approval_not_required"
  | "not_eligible"
  | "not_approvable"
  | "self_approval"
  | "already_decided"
  | "anonymous";

/** Error codes `POST /records/{id}/decisions` may return. */
export type DecisionErrorCode =
  | "digest_changed"
  | "already_decided"
  | "policy_missing"
  | "approval_not_required"
  | "not_approvable"
  | "not_eligible"
  | "self_approval"
  | "record_not_found";
