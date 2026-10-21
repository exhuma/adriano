/**
 * Approval-state view-model helpers: the decision-page status chip,
 * its one-sentence explanation, the decision-action history label,
 * the divergence banner's label, the "why can't I decide this" copy,
 * and {@link approvalDisplayLabel}, the single place a record's
 * approval chip is derived (decision or erratum, blocked or not).
 * Split from the former `utils/labels.ts` by domain
 * (module-code-structure-limits); see `index.ts`.
 */
import type {
  DecideBlockedCode,
  DecisionAction,
  DivergenceKind,
  PolicyStatus,
} from "@/types/approval";
import type {
  ApprovalStateCode,
  RecordKind,
  RecordState,
} from "@/types/records";

import { erratumStatusLabel } from "./errata";
import { BLOCKED_EXPLANATION, BLOCKED_STATUS_LABEL } from "./shared";
import type { StatusLabel } from "./shared";

/**
 * Describe a record's approval state for display.
 *
 * :param state: Approval state of the record's current content.
 * :param kind: Whether the record is published or a candidate (only
 *     used to distinguish the two "accepted" labels).
 * :returns: Icon, label text, and colour.
 */
export function approvalStateLabel(
  state: ApprovalStateCode,
  kind: RecordState,
): StatusLabel {
  switch (state) {
    case "accepted":
      return kind === "candidate"
        ? {
            icon: "mdi-check-decagram",
            text: "Accepted — candidate",
            color: "success",
          }
        : {
            icon: "mdi-check-decagram",
            text: "Accepted — published",
            color: "success",
          };
    case "pending":
      return {
        icon: "mdi-clock-outline",
        text: "Pending approval",
        color: "warning",
      };
    case "rejected":
      return { icon: "mdi-close-circle", text: "Rejected", color: "error" };
    case "changed_since_acceptance":
      return {
        icon: "mdi-alert-circle",
        text: "Changed since acceptance",
        color: "warning",
      };
    case "not_required":
      return { icon: "mdi-information-outline", text: "Approval not required" };
    case "policy_missing":
      return {
        icon: "mdi-help-circle-outline",
        text: "Approval policy not configured",
        color: "warning",
      };
    default:
      return { icon: "mdi-help-circle-outline", text: state };
  }
}

/**
 * Explain a record's approval state in one reader-facing sentence,
 * distinguishing an unconfigured/invalid policy from an ordinary
 * pending review so a missing configuration is never mistaken for a
 * reviewer delay (SPEC.md "Independent approval and sign-off
 * workflow"). When the content itself cannot be decided (a content
 * problem, not a policy or reviewer one -- R-02), this overrides the
 * ordinary "Awaiting review" wording, matching the "Blocked" chip
 * from {@link approvalDisplayLabel}.
 *
 * :param state: Approval state of the record's current content.
 * :param policyStatus: Configuration status of the global policy.
 * :param recordKind: Decision or erratum; picks the wording.
 * :param approvable: Whether the content itself can be decided at
 *     all, independent of policy/reviewer (`ApprovalOut.approvable`).
 * :returns: A one-sentence explanation.
 */
export function approvalStateExplanation(
  state: ApprovalStateCode,
  policyStatus: PolicyStatus,
  recordKind: RecordKind = "decision",
  approvable = true,
): string {
  if (!approvable) {
    return BLOCKED_EXPLANATION;
  }
  if (state === "policy_missing" || policyStatus !== "configured") {
    return policyStatus === "invalid"
      ? "The configured approval policy is invalid — an operator " +
        "must fix it."
      : "No approval policy is configured — an operator must " +
        "configure one.";
  }
  if (recordKind === "erratum") {
    switch (state) {
      case "pending":
        return "This erratum is reported and awaits verification.";
      case "rejected":
        return "This erratum was rejected for this exact content.";
      case "changed_since_acceptance":
        return "This erratum's content changed since it was verified " +
          "— the verified version differs from the current content.";
      case "not_required":
        return "This erratum does not require review.";
      case "accepted":
        return "This erratum was verified for this exact content.";
      default:
        return "";
    }
  }
  switch (state) {
    case "pending":
      return "Awaiting review.";
    case "rejected":
      return "Rejected for this exact content.";
    case "changed_since_acceptance":
      return "Changed since acceptance — the accepted version differs " +
        "from the current content.";
    case "not_required":
      return "Approval not required by policy.";
    case "accepted":
      return "Accepted for this exact content.";
    default:
      return "";
  }
}

/**
 * Describe a formal decision action for display (history table).
 *
 * :param action: Accepted or rejected.
 * :param recordKind: Whether the record is a normal decision or an
 *     erratum; an erratum's "accepted" action reads "Verified" (RFC
 *     report/verify/reject vocabulary), matching `erratumStatusLabel`.
 * :returns: Icon, label text, and colour.
 */
export function decisionActionLabel(
  action: DecisionAction,
  recordKind: RecordKind = "decision",
): StatusLabel {
  if (action === "accepted") {
    return recordKind === "erratum"
      ? { icon: "mdi-check-circle", text: "Verified", color: "success" }
      : { icon: "mdi-check-circle", text: "Accepted", color: "success" };
  }
  return { icon: "mdi-close-circle", text: "Rejected", color: "error" };
}

/**
 * Describe a divergence between published and accepted/candidate
 * content for the record page's divergence banner.
 *
 * :param kind: Which divergence applies.
 * :returns: Icon and label text (the banner supplies the message).
 */
export function divergenceLabel(kind: DivergenceKind): StatusLabel {
  return kind === "published_not_accepted"
    ? {
        icon: "mdi-alert-circle-outline",
        text: "Published content not accepted",
        color: "warning",
      }
    : {
        icon: "mdi-alert-circle-outline",
        text: "Published content differs",
        color: "warning",
      };
}

/**
 * Describe a record's approval state for display, overriding to the
 * neutral "Blocked" status whenever the content itself cannot be
 * decided (R-02). This is the single place a record's approval chip
 * is derived on the record page (the sidebar summary card, the
 * approval card, the siblings card, the divergence banner's
 * competing candidates and each erratum entry -- every payload
 * carries its own `approvable`); search rows use the shorter
 * {@link import("./search").searchApprovalStateLabel}/
 * {@link import("./search").searchErratumStatusLabel}, which apply
 * the same "Blocked" override.
 *
 * `approvable` is distinct from the per-viewer
 * `decide_blocked_code`: a reader is blocked by `not_eligible` even
 * on perfectly valid content, but `approvable` is the same for every
 * viewer, so it is the right signal for a status chip everyone sees
 * the same way.
 *
 * :param approval: The state and content-approvability of the
 *     record's current content.
 * :param kind: Published or candidate; picks the "accepted" wording.
 * :param recordKind: Decision or erratum; picks the vocabulary.
 * :param ref: Source ref (branch/label) for a candidate erratum.
 * :returns: Icon, label text, and colour.
 */
export function approvalDisplayLabel(
  approval: { state: ApprovalStateCode; approvable: boolean },
  kind: RecordState,
  recordKind: RecordKind = "decision",
  ref?: string,
): StatusLabel {
  if (!approval.approvable) {
    return BLOCKED_STATUS_LABEL;
  }
  return recordKind === "erratum"
    ? erratumStatusLabel(approval.state, kind, ref)
    : approvalStateLabel(approval.state, kind);
}

/**
 * Plain-language message for every stable reason the caller cannot
 * decide a record now (`ApprovalOut.decide_blocked_code`;
 * docs/ui-review R-10). Replaces the raw `decide_blocked_reason`
 * text ("not a reviewer: the approval policy lists neither this
 * user nor any of their roles") that used to be shown verbatim.
 *
 * `not_eligible` (a reader, or a signed-in user the policy does not
 * list) intentionally gets the shortest, most muted line -- "a muted
 * 'Only reviewers can approve' style line is enough" (Task 8). Every
 * other code's backend message is fully static, except
 * `not_approvable`, whose nested reader-facing reason has no code of
 * its own; the caller shows that raw text separately, in a secondary
 * "Details" position (shown only when the page's issues card has not
 * already explained it, P11-R-07), rather than this function trying
 * to parse it out of `decide_blocked_reason`.
 *
 * :param code: The stable blocker code, or `null` when not blocked.
 * :returns: The message, or `null` for `null`/an unrecognised code
 *     (the caller falls back to the raw `decide_blocked_reason`).
 */
export function decideBlockedLabel(
  code: DecideBlockedCode | null,
): string | null {
  if (code === null) {
    return null;
  }
  const messages: Record<DecideBlockedCode, string> = {
    policy_missing:
      "No approval policy is configured, so nothing can be decided yet.",
    approval_not_required: "This content does not require approval.",
    not_eligible: "Only reviewers can approve this.",
    not_approvable: BLOCKED_EXPLANATION,
    self_approval: "You wrote this content, so you can't decide it yourself.",
    already_decided:
      "This exact content was already decided and can't be decided again.",
    anonymous: "Sign in as a reviewer to decide this.",
  };
  return messages[code] ?? null;
}
