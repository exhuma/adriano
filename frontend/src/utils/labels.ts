/**
 * Pure view-model helpers mapping backend enum values to an
 * icon + text pair, so status is never shown by colour alone
 * (module-ux-principles "Do not rely on color alone"). Every
 * function here is a pure mapping with no I/O, reused by both
 * `SearchView`/`RecordView`/`SourcesView` and their tests.
 */
import type { DecisionAction, DivergenceKind, PolicyStatus } from "@/types/approval";
import type {
  ApprovalStateCode,
  DisplayStatus,
  ErratumType,
  IssueCountsOut,
  RecordKind,
  RecordState,
} from "@/types/records";
import type { PollStatus } from "@/types/sources";

/** An icon + text + colour triple rendered as a `StatusChip`. */
export interface StatusLabel {
  /** Material Design Icons name. */
  icon: string;
  /** Visible and accessible label text. */
  text: string;
  /** Vuetify theme colour token, or `undefined` for a neutral chip. */
  color?: string;
}

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
        ? { icon: "mdi-check-decagram", text: "Accepted — candidate", color: "success" }
        : { icon: "mdi-check-decagram", text: "Accepted — published", color: "success" };
    case "pending":
      return { icon: "mdi-clock-outline", text: "Pending approval", color: "warning" };
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
 * workflow").
 *
 * :param state: Approval state of the record's current content.
 * :param policyStatus: Configuration status of the global policy.
 * :returns: A one-sentence explanation.
 */
export function approvalStateExplanation(
  state: ApprovalStateCode,
  policyStatus: PolicyStatus,
  recordKind: RecordKind = "decision",
): string {
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
 * :returns: Icon, label text, and colour.
 */
export function decisionActionLabel(action: DecisionAction): StatusLabel {
  return action === "accepted"
    ? { icon: "mdi-check-circle", text: "Accepted", color: "success" }
    : { icon: "mdi-close-circle", text: "Rejected", color: "error" };
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
    ? { icon: "mdi-alert-circle-outline", text: "Published content not accepted", color: "warning" }
    : { icon: "mdi-alert-circle-outline", text: "Published content differs", color: "warning" };
}

/**
 * Describe a record's candidate/published state for display.
 *
 * :param kind: Lifecycle state of the record row.
 * :param ref: Source ref (branch/label), shown for candidates.
 * :returns: Icon, label text, and colour.
 */
export function recordStateLabel(kind: RecordState, ref?: string): StatusLabel {
  if (kind === "published") {
    return { icon: "mdi-check-circle-outline", text: "Published" };
  }
  return {
    icon: "mdi-source-branch",
    text: ref ? `Candidate (${ref})` : "Candidate",
    color: "info",
  };
}

/**
 * Describe a record's own kind (a decision or an erratum correcting
 * one) for the detail page header chip. Distinct from
 * `recordStateLabel`, which labels published/candidate.
 *
 * :param kind: Decision or erratum.
 * :returns: Icon and label text.
 */
export function recordKindTypeLabel(kind: RecordKind): StatusLabel {
  return kind === "erratum"
    ? { icon: "mdi-file-alert-outline", text: "Erratum" }
    : { icon: "mdi-file-document-outline", text: "Decision" };
}

/**
 * Describe one erratum's own approval state for display (RFC-style
 * report/verify/reject vocabulary, distinct from `approvalStateLabel`'s
 * decision wording).
 *
 * :param state: Approval state of the erratum's current content.
 * :param kind: Whether this erratum row is published or a candidate;
 *     a candidate additionally shows a "Proposed" suffix.
 * :param ref: Source ref (branch/label) for a candidate; shown in the
 *     "Proposed (branch …)" suffix when known.
 * :returns: Icon, label text, and colour.
 */
export function erratumStatusLabel(
  state: ApprovalStateCode,
  kind: RecordState,
  ref?: string,
): StatusLabel {
  const base = ((): StatusLabel => {
    switch (state) {
      case "pending":
      case "policy_missing":
        return { icon: "mdi-clock-outline", text: "Reported", color: "warning" };
      case "accepted":
        return { icon: "mdi-check-decagram", text: "Verified", color: "success" };
      case "rejected":
        return { icon: "mdi-close-circle", text: "Rejected", color: "error" };
      case "changed_since_acceptance":
        return {
          icon: "mdi-alert-circle",
          text: "Changed since verification",
          color: "warning",
        };
      case "not_required":
        return {
          icon: "mdi-information-outline",
          text: "Published (no review required)",
        };
      default:
        return { icon: "mdi-help-circle-outline", text: state };
    }
  })();
  if (kind !== "candidate") {
    return base;
  }
  const proposed = ref ? `Proposed (branch ${ref})` : "Proposed";
  return { ...base, text: `${base.text} — ${proposed}` };
}

/**
 * Describe an erratum's reported correction type for display.
 *
 * :param type: Technical or editorial, or `null` when unset.
 * :returns: Icon and label text.
 */
export function erratumTypeLabel(type: ErratumType | null): StatusLabel {
  switch (type) {
    case "technical":
      return { icon: "mdi-wrench-outline", text: "Technical" };
    case "editorial":
      return { icon: "mdi-pencil-outline", text: "Editorial" };
    default:
      return { icon: "mdi-help-circle-outline", text: "Type not set" };
  }
}

/**
 * Describe a record's derived display status for the detail page.
 *
 * :param status: Status derived from inbound lifecycle links.
 * :returns: Icon, label text, and colour.
 */
export function displayStatusLabel(status: DisplayStatus): StatusLabel {
  switch (status) {
    case "active":
      return { icon: "mdi-check-circle", text: "Active", color: "success" };
    case "updated":
      return {
        icon: "mdi-arrow-up-bold-circle-outline",
        text: "Updated",
        color: "warning",
      };
    case "obsoleted":
      return {
        icon: "mdi-archive-arrow-down-outline",
        text: "Obsoleted",
        color: "error",
      };
    default:
      return { icon: "mdi-help-circle-outline", text: status };
  }
}

/**
 * Describe a registration's last poll outcome for display.
 *
 * :param status: Outcome of the latest poll.
 * :param stale: Whether freshness has crossed the configured
 *     threshold (or the registration is disabled/never succeeded).
 * :returns: Icon, label text, and colour.
 */
export function pollStatusLabel(status: PollStatus, stale: boolean): StatusLabel {
  const base = ((): StatusLabel => {
    switch (status) {
      case "never":
        return { icon: "mdi-help-circle-outline", text: "Never polled" };
      case "ok":
        return { icon: "mdi-check-circle", text: "OK", color: "success" };
      case "partial":
        return { icon: "mdi-alert", text: "Partial", color: "warning" };
      case "failed":
        return { icon: "mdi-close-circle", text: "Failed", color: "error" };
      case "disabled":
        return { icon: "mdi-cancel", text: "Disabled" };
      default:
        return { icon: "mdi-help-circle-outline", text: status };
    }
  })();
  if (stale && status !== "failed") {
    return { icon: "mdi-clock-alert-outline", text: `${base.text} (stale)`, color: "warning" };
  }
  return base;
}

/**
 * Describe an outbound or inbound record-link type for display, on
 * the record detail page's links/errata cards and its "superseded
 * by" note (shared so both name the same relationship the same way).
 *
 * :param type: Outbound (`LinkType`) or inbound (`InboundType`) link
 *     type name.
 * :returns: A short display label, or the raw type when unknown.
 */
export function linkTypeLabel(type: string): string {
  switch (type) {
    case "updates":
      return "Updates";
    case "obsoletes":
      return "Obsoletes";
    case "corrects":
      return "Corrects";
    case "updated_by":
      return "Updated by";
    case "obsoleted_by":
      return "Obsoleted by";
    default:
      return type;
  }
}

/**
 * Summarise a record's validation issue counts for display.
 *
 * :param counts: Error and warning counts.
 * :returns: `null` when there are no issues; otherwise an
 *     icon/text/colour triple with an accessible count description.
 */
export function issueIndicatorLabel(counts: IssueCountsOut): StatusLabel | null {
  if (counts.error === 0 && counts.warning === 0) {
    return null;
  }
  const parts: string[] = [];
  if (counts.error > 0) {
    parts.push(`${counts.error} error${counts.error === 1 ? "" : "s"}`);
  }
  if (counts.warning > 0) {
    parts.push(`${counts.warning} warning${counts.warning === 1 ? "" : "s"}`);
  }
  const text = parts.join(", ");
  if (counts.error > 0) {
    return { icon: "mdi-alert-circle", text, color: "error" };
  }
  return { icon: "mdi-alert", text, color: "warning" };
}
