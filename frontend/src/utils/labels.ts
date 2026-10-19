/**
 * Pure view-model helpers mapping backend enum values to an
 * icon + text pair, so status is never shown by colour alone
 * (module-ux-principles "Do not rely on color alone"). Every
 * function here is a pure mapping with no I/O, reused by both
 * `SearchView`/`RecordView`/`SourcesView` and their tests.
 */
import type {
  ApprovalStateCode,
  DisplayStatus,
  IssueCountsOut,
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
