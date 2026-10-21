/**
 * Search-result-row view-model helpers: the compact decision/erratum
 * status chips (1-2 words, neutral "pending" text, no candidate/
 * published suffix duplicated inside the chip text) and the
 * candidate-branch secondary text. Split from the former
 * `utils/labels.ts` by domain (module-code-structure-limits); see
 * `index.ts`.
 */
import type { ApprovalStateCode, RecordState } from "@/types/records";

import { BLOCKED_STATUS_LABEL } from "./shared";
import type { StatusLabel } from "./shared";

/**
 * Describe a record's candidate/published state for a search result
 * row.
 *
 * Unlike {@link import("./records").recordStateLabel}, "Published"
 * (the default lifecycle state) is hidden entirely rather than shown
 * as a grey chip (a status chip is shown only when it differs from the
 * default), and
 * a candidate's branch is left out of the chip text -- it is shown
 * once as plain text instead ({@link candidateBranchText}), per S-05.
 *
 * :param kind: Lifecycle state of the record row.
 * :returns: Icon, label text and colour for a candidate; `null` for
 *     a published record (no chip).
 */
export function searchRecordStateLabel(kind: RecordState): StatusLabel | null {
  if (kind === "published") {
    return null;
  }
  return { icon: "mdi-source-branch", text: "Candidate", color: "info" };
}

/**
 * The branch/ref shown once as secondary text in a search row's
 * metadata line, for a candidate record (S-05: do not also repeat it
 * inside a chip's text).
 *
 * :param kind: Lifecycle state of the record row.
 * :param ref: Source ref (branch/label).
 * :returns: `null` for a published record or a missing ref;
 *     otherwise "Branch: <ref>".
 */
export function candidateBranchText(
  kind: RecordState,
  ref?: string,
): string | null {
  if (kind !== "candidate" || !ref) {
    return null;
  }
  return `Branch: ${ref}`;
}

/**
 * Describe a decision's approval state for a search result row.
 *
 * A search-row-specific sibling of
 * {@link import("./approval").approvalStateLabel}: every chip stays
 * to 1-2 words (the full wording moves to `ariaLabel`, so the row
 * link's accessible name still states it in full), the
 * candidate/published distinction is dropped (it already has its own
 * chip, {@link searchRecordStateLabel}), and "pending" loses its
 * colour -- "Pending approval"
 * stays visible on search rows but as neutral text; strong colour is
 * reserved for issues (error/warning) and rejection.
 *
 * Content that cannot be decided at all (`approvable === false`,
 * R-02) shows the same neutral "Blocked" status as the record page
 * ({@link import("./approval").approvalDisplayLabel}), never
 * "Pending approval".
 *
 * :param state: Approval state of the record's current content.
 * :param approvable: Whether the content can be decided at all
 *     (`SearchItemOut.approvable`).
 * :returns: Icon, label text, and colour (neutral chips omit it).
 */
export function searchApprovalStateLabel(
  state: ApprovalStateCode,
  approvable = true,
): StatusLabel {
  if (!approvable) {
    return BLOCKED_STATUS_LABEL;
  }
  switch (state) {
    case "accepted":
      return { icon: "mdi-check-decagram", text: "Accepted", color: "success" };
    case "pending":
      return { icon: "mdi-clock-outline", text: "Pending approval" };
    case "rejected":
      return { icon: "mdi-close-circle", text: "Rejected", color: "error" };
    case "changed_since_acceptance":
      return {
        icon: "mdi-alert-circle",
        text: "Changed",
        color: "warning",
        ariaLabel: "Changed since acceptance",
      };
    case "not_required":
      return {
        icon: "mdi-information-outline",
        text: "Not required",
        ariaLabel: "Approval not required",
      };
    case "policy_missing":
      return {
        icon: "mdi-help-circle-outline",
        text: "No policy",
        color: "warning",
        ariaLabel: "Approval policy not configured",
      };
    default:
      return { icon: "mdi-help-circle-outline", text: state };
  }
}

/**
 * Describe an erratum's approval state for a search result row.
 *
 * The search-row sibling of
 * {@link import("./errata").erratumStatusLabel}: same 1-2 word and
 * neutral-pending rules as {@link searchApprovalStateLabel}
 * (RFC-style report/verify/reject wording), and the candidate
 * "Proposed (branch …)" suffix is dropped -- it is covered by
 * {@link searchRecordStateLabel} and {@link candidateBranchText}
 * instead, so the branch is not repeated twice on one row (S-05).
 *
 * :param state: Approval state of the erratum's current content.
 * :param approvable: Whether the content can be decided at all; when
 *     not, the neutral "Blocked" status replaces "Reported" (R-02).
 * :returns: Icon, label text, and colour (neutral chips omit it).
 */
export function searchErratumStatusLabel(
  state: ApprovalStateCode,
  approvable = true,
): StatusLabel {
  if (!approvable) {
    return BLOCKED_STATUS_LABEL;
  }
  switch (state) {
    case "pending":
      return { icon: "mdi-clock-outline", text: "Reported" };
    case "policy_missing":
      return {
        icon: "mdi-clock-outline",
        text: "Reported",
        color: "warning",
        ariaLabel: "Reported — approval policy not configured",
      };
    case "accepted":
      return { icon: "mdi-check-decagram", text: "Verified", color: "success" };
    case "rejected":
      return { icon: "mdi-close-circle", text: "Rejected", color: "error" };
    case "changed_since_acceptance":
      return {
        icon: "mdi-alert-circle",
        text: "Changed",
        color: "warning",
        ariaLabel: "Changed since verification",
      };
    case "not_required":
      return {
        icon: "mdi-information-outline",
        text: "Not required",
        ariaLabel: "Published — no review required",
      };
    default:
      return { icon: "mdi-help-circle-outline", text: state };
  }
}
