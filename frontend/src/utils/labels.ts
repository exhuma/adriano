/**
 * Pure view-model helpers mapping backend enum values to an
 * icon + text pair, so status is never shown by colour alone
 * (module-ux-principles "Do not rely on color alone"). Every
 * function here is a pure mapping with no I/O, reused by both
 * `SearchView`/`RecordView`/`SourcesView` and their tests.
 */
import type {
  DecideBlockedCode,
  DecisionAction,
  DivergenceKind,
  PolicyStatus,
} from "@/types/approval";
import type {
  ApprovalStateCode,
  DisplayStatus,
  ErrataSummaryOut,
  ErratumType,
  IssueCode,
  IssueCountsOut,
  RecordKind,
  RecordState,
} from "@/types/records";
import type { PollStatus } from "@/types/sources";

/** An icon + text + colour triple rendered as a `StatusChip`. */
export interface StatusLabel {
  /** Material Design Icons name. */
  icon: string;
  /** Visible label text. */
  text: string;
  /** Vuetify theme colour token, or `undefined` for a neutral chip. */
  color?: string;
  /**
   * Full meaning announced to assistive tech when `text` has been
   * shortened for space (`StatusChip`'s `ariaLabel` prop); falls
   * back to `text` when omitted, so it stays optional here.
   */
  ariaLabel?: string;
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
 * Neutral status for content that cannot be decided at all because
 * of a content problem (R-02), e.g. a missing/invalid `uuid` or
 * invalid encoding (`ApprovalOut.approvable === false`). The icon is
 * error-ish (an alert glyph) but the chip carries no colour: text
 * and icon carry the meaning, not an error-red fill
 * (phases/11-ui-ux-updates.md: "a neutral chip with an error-ish
 * icon [...] not the error colour as the only signal").
 */
const BLOCKED_STATUS_LABEL: StatusLabel = {
  icon: "mdi-alert-circle-outline",
  text: "Blocked",
  ariaLabel: "Blocked — this content cannot be decided",
};

/** Explanation sentence paired with {@link BLOCKED_STATUS_LABEL}. */
const BLOCKED_EXPLANATION =
  "This content can't be decided until its problems are fixed.";

/**
 * Describe a record's approval state for display, overriding to the
 * neutral "Blocked" status whenever the content itself cannot be
 * decided (R-02). This is the single place a record's approval chip
 * is derived everywhere it appears (the sidebar summary card and the
 * approval card); search rows use {@link searchApprovalStateLabel}
 * directly instead, since the search payload carries no `approvable`
 * field to derive "Blocked" from.
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
 * Describe a record's candidate/published state for a search result
 * row.
 *
 * Unlike {@link recordStateLabel}, "Published" (the default lifecycle
 * state) is hidden entirely rather than shown as a grey chip
 * (phases/11-ui-ux-updates.md "Chip visibility rule": a status chip
 * is shown only when it differs from the default), and a candidate's
 * branch is left out of the chip text -- it is shown once as plain
 * text instead ({@link candidateBranchText}), per S-05.
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
 * A search-row-specific sibling of {@link approvalStateLabel}: every
 * chip stays to 1-2 words (the full wording moves to `ariaLabel`, so
 * the row link's accessible name still states it in full), the
 * candidate/published distinction is dropped (it already has its own
 * chip, {@link searchRecordStateLabel}), and "pending" loses its
 * colour -- phases/11-ui-ux-updates.md Decision 2: "Pending approval"
 * stays visible on search rows but as neutral text; strong colour is
 * reserved for issues (error/warning) and rejection.
 *
 * :param state: Approval state of the record's current content.
 * :returns: Icon, label text, and colour (neutral chips omit it).
 */
export function searchApprovalStateLabel(
  state: ApprovalStateCode,
): StatusLabel {
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
 * The search-row sibling of {@link erratumStatusLabel}: same 1-2 word
 * and neutral-pending rules as {@link searchApprovalStateLabel}
 * (RFC-style report/verify/reject wording), and the candidate
 * "Proposed (branch …)" suffix is dropped -- it is covered by
 * {@link searchRecordStateLabel} and {@link candidateBranchText}
 * instead, so the branch is not repeated twice on one row (S-05).
 *
 * :param state: Approval state of the erratum's current content.
 * :returns: Icon, label text, and colour (neutral chips omit it).
 */
export function searchErratumStatusLabel(
  state: ApprovalStateCode,
): StatusLabel {
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
 * `not_approvable`, whose nested reader-facing reason (e.g. "the
 * record has no valid `uuid`") has no code of its own; the caller
 * shows that raw text separately, in a secondary "Details" position,
 * rather than this function trying to parse it out of
 * `decide_blocked_reason`.
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

/**
 * Plain-language headline for a stable validation issue code
 * (`IssueOut.code`; docs/ui-review R-10, Task 8). The backend's own
 * `message` is kept in full alongside it ({@link validationIssueText}
 * composes the two) -- these headlines summarise *what kind* of
 * problem the code is, while the per-instance detail (which field,
 * which UUID, which heading) only exists in the free-text message
 * the backend sends, which is never parsed to extract it.
 *
 * :param code: The stable issue code.
 * :returns: A short, human headline.
 */
export function issueCodeLabel(code: IssueCode): string {
  const headlines: Record<IssueCode, string> = {
    bad_yaml: "The file's front matter is not valid YAML",
    missing_frontmatter: "The file has no front matter block",
    missing_uuid: "The record has no `uuid`",
    bad_uuid: "The record's `uuid` is not valid",
    bad_date: "The record's date is not valid",
    missing_date: "The record has no decision date",
    unknown_field: "The front matter has a field the catalog does not use",
    bad_field_type: "A front-matter field has an unexpected value",
    duplicate_uuid: "Another record already uses this `uuid`",
    missing_target: "A linked record could not be found",
    ambiguous_target: "A link matches more than one record",
    legacy_alias: "This field is a legacy alias of a newer one",
    legacy_signoff: "This uses the old, unverified sign-off field",
    corrects_on_non_erratum:
      "A `corrects` field was used outside an erratum, which is no " +
      "longer supported",
    erratum_without_target:
      "This erratum does not say which decision it corrects",
    bad_encoding: "The file is not valid UTF-8 text",
    bad_erratum_type: "The erratum's `type` is missing or not recognised",
    erratum_missing_corrected_text:
      "The erratum is missing its corrected text",
    erratum_unknown_section_heading:
      "The erratum has a section heading the catalog does not recognise",
    erratum_duplicate_section: "The erratum repeats the same section twice",
    erratum_targets_itself: "An erratum can't correct itself",
    erratum_relationship_ignored:
      "A relationship field on this erratum is ignored",
    erratum_target_is_erratum:
      "This erratum corrects another erratum, which is not supported",
    legacy_erratum_format:
      "This uses the old erratum format, which is no longer supported",
    obsolete_kind_field: "The `kind` field is no longer needed",
  };
  return headlines[code];
}

/**
 * Compose one validation issue's display text: the plain-language
 * headline followed by the backend's own actionable message, so no
 * per-instance detail (field name, value, target) is ever lost or
 * parsed out of free text.
 *
 * :param code: The stable issue code.
 * :param message: The backend's own message for this issue.
 * :returns: "<headline> — <message>".
 */
export function validationIssueText(code: IssueCode, message: string): string {
  return `${issueCodeLabel(code)} — ${message}`;
}

/** Stable poll-problem codes (`PollProblem.code`; see
 *  `backend/app/services/polling.py` and `poll_plan.py`), mapped to a
 *  plain-language headline. The field is untyped JSON on the wire
 *  (`SourceOut.last_error`), not a generated enum, so this is keyed
 *  by the documented string values rather than a TypeScript union. */
const POLL_PROBLEM_HEADLINES: Record<string, string> = {
  source_error: "Couldn't reach the source",
  internal_error: "An unexpected error interrupted the poll",
  projects_incomplete:
    "The project list could not be fully read; some projects may be missing",
  listing_failed: "Couldn't list the files in this project",
  listing_incomplete:
    "The file list could not be fully read; some files may be missing",
  fetch_failed: "Couldn't fetch a changed file",
  ownership_conflict: "Skipped — already handled by an earlier registration",
  not_pollable: "This registration can't be polled",
};

/**
 * Plain-language headline for a poll-problem code (docs/ui-review
 * R-10, Task 8). The backend's own message, which is kept alongside
 * it as secondary "Details" text by the caller, carries the
 * per-instance specifics (which project, which file, the underlying
 * source error).
 *
 * :param code: The stable code from one `problems[]` entry, if any.
 * :returns: The headline, or `null` for a missing/unrecognised code
 *     (the caller falls back to the raw message alone).
 */
export function pollProblemLabel(code: string | undefined): string | null {
  if (code === undefined) {
    return null;
  }
  return POLL_PROBLEM_HEADLINES[code] ?? null;
}
