/**
 * Erratum view-model helpers: an erratum's own RFC-style
 * report/verify/reject status chip, its technical/editorial type
 * chip, and the header/section errata-count copy. Split from the
 * former `utils/labels.ts` by domain (module-code-structure-limits);
 * see `index.ts`.
 */
import type {
  ApprovalStateCode,
  ErrataSummaryOut,
  ErratumType,
  RecordState,
} from "@/types/records";

import type { StatusLabel } from "./shared";

/**
 * Describe one erratum's own approval state for display (RFC-style
 * report/verify/reject vocabulary, distinct from `approvalStateLabel`'s
 * decision wording).
 *
 * :param state: Approval state of the erratum's current content.
 * :param kind: Whether this erratum row is published or a candidate;
 *     a candidate additionally shows a "Proposed" suffix.
 * :param ref: Source ref (branch/label) for a candidate; shown in the
 *     "Proposed (ref …)" suffix when known.
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
        return {
          icon: "mdi-clock-outline",
          text: "Reported",
          color: "warning",
        };
      case "accepted":
        return {
          icon: "mdi-check-decagram",
          text: "Verified",
          color: "success",
        };
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
  const proposed = ref ? `Proposed (ref ${ref})` : "Proposed";
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
 * Singular/plural noun for an erratum count ("1 erratum" vs. "2
 * errata"). Shared by the header's errata link and the errata
 * section heading, so the two never pick different wording for the
 * same count.
 *
 * :param count: Number of errata.
 * :returns: "erratum" for 1, otherwise "errata".
 */
export function pluralizeErrata(count: number): string {
  return count === 1 ? "erratum" : "errata";
}

/**
 * The record header metadata line's errata link text (e.g.
 * "1 erratum" or "2 proposed errata"), replacing the old full-
 * sentence "has N errata" banner with a short link (R-04: say each
 * fact once -- the dedicated `ErrataSection` already covers the
 * detail). Counts published errata when any are published; falls
 * back to the proposed count when nothing is published yet, so the
 * link never reads "0 errata".
 *
 * :param summary: Errata counts for this decision.
 * :returns: The count phrase, or `null` when there are no errata at
 *     all (published or proposed).
 */
export function errataHeaderLinkText(summary: ErrataSummaryOut): string | null {
  if (summary.total > 0) {
    return `${summary.total} ${pluralizeErrata(summary.total)}`;
  }
  if (summary.proposed > 0) {
    return `${summary.proposed} proposed ${pluralizeErrata(summary.proposed)}`;
  }
  return null;
}

/**
 * The errata section's heading text (e.g. "Errata — 2 errata ·
 * 1 proposed", or "Errata — 1 proposed" when nothing is published
 * yet). Never renders a bare "(0)" count (R-13): each half of the
 * heading is omitted entirely, rather than shown as zero, when that
 * half's count is zero.
 *
 * :param published: Count of published errata.
 * :param proposed: Count of proposed (candidate) errata.
 * :returns: The heading text. The caller only renders it when at
 *     least one of the two counts is positive.
 */
export function errataHeadingText(published: number, proposed: number): string {
  const parts: string[] = [];
  if (published > 0) {
    parts.push(`${published} ${pluralizeErrata(published)}`);
  }
  if (proposed > 0) {
    parts.push(`${proposed} proposed`);
  }
  return `Errata — ${parts.join(" · ")}`;
}
