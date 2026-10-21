/**
 * Record-identity view-model helpers: published/candidate state, the
 * decision-vs-erratum kind chip, the derived lifecycle status
 * (active/updated/obsoleted), and outbound/inbound relationship-type
 * labels. Split from the former `utils/labels.ts` by domain
 * (module-code-structure-limits); see `index.ts`.
 */
import type {
  DisplayStatus,
  RecordKind,
  RecordState,
} from "@/types/records";

import type { StatusLabel } from "./shared";

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
