/**
 * View-model computeds for the record detail page, extracted from
 * `RecordView.vue` so the view stays a thin page shell (banner/link
 * glue; module-code-structure-limits: extract a cohesive unit along
 * a real seam, not a mechanical split). Every value here is a pure
 * derivation from the loaded `RecordDetail`; none of it does I/O.
 */
import { computed, type Ref } from "vue";

import { ApiError } from "@/api";
import type { DecisionAction } from "@/types/approval";
import type { RecordDetail } from "@/types/records";
import { forbiddenText, isForbidden } from "@/utils/apiErrors";
import { hasComparableRevision } from "@/utils/diff";
import { freshnessBannerText, provenanceText } from "@/utils/freshness";
import {
  errataHeaderLinkText,
  issueIndicatorLabel,
  recordKindTypeLabel,
  recordStateLabel,
  type StatusLabel,
} from "@/utils/labels";

/**
 * Describe a failed record load for the page's error state.
 *
 * :param error: The thrown error (any type; only `ApiError` and a
 *     "forbidden" response are distinguished).
 * :returns: A reader-facing sentence.
 */
export function describeRecordLoadError(error: unknown): string {
  if (isForbidden(error)) {
    return forbiddenText(error);
  }
  if (error instanceof ApiError) {
    return (
      `The record could not be loaded (status ${error.status}). ` +
      "Check your connection and try again."
    );
  }
  return "The record could not be loaded. Check your connection and try again.";
}

/**
 * The snackbar text for a just-recorded decision: erratum wording
 * ("Erratum verified."/"Erratum rejected.") when the viewed record is
 * itself an erratum, plain decision wording otherwise.
 *
 * :param action: The decision just recorded.
 * :param isErratum: Whether the viewed record is an erratum.
 * :returns: The snackbar message.
 */
export function decidedSnackbarText(
  action: DecisionAction,
  isErratum: boolean,
): string {
  if (isErratum) {
    return action === "accepted" ? "Erratum verified." : "Erratum rejected.";
  }
  return action === "accepted"
    ? "Decision recorded: accepted."
    : "Decision recorded: rejected.";
}

/** Everything `RecordView.vue` derives from the loaded record,
 *  beyond the raw `RecordDetail` itself. */
export interface RecordDetailView {
  /** Error/warning validation issue counts. */
  issueCounts: Readonly<Ref<{ error: number; warning: number }>>;
  /** Validation issue-count chip, or `null` when there are none. */
  issueIndicator: Readonly<Ref<StatusLabel | null>>;
  /** Candidate chip, or `null` for published (the default state is
   *  never shown as a chip, R-05). */
  recordKindLabel: Readonly<Ref<StatusLabel | null>>;
  /** Erratum chip, or `null` for a plain decision (the default kind
   *  is never shown as a chip, R-05), distinct from `recordKindLabel`. */
  recordTypeLabel: Readonly<Ref<StatusLabel | null>>;
  /** Sentence distinguishing candidate (with branch) from published. */
  provenanceSentence: Readonly<Ref<string>>;
  /** The header's errata link text, or `null` when the decision has
   *  no errata at all (R-04). */
  errataLinkText: Readonly<Ref<string | null>>;
  /** The stale/failed freshness banner's text, or `null`. */
  freshnessBanner: Readonly<Ref<string | null>>;
  /** Whether to show the accepted-candidate note (works for both a
   *  decision and an erratum; `RecordHeader` picks the wording). */
  showAcceptedCandidateNote: Readonly<Ref<boolean>>;
  /** The page's `h1` text: "Erratum for <target title>" once a
   *  resolved erratum's target is known, otherwise the record's own
   *  stored title. */
  pageTitle: Readonly<Ref<string>>;
  /** Subtitle line under the `h1` (the erratum's section), shown
   *  only alongside the resolved-erratum title above. */
  pageSubtitle: Readonly<Ref<string | null>>;
  /** Inbound `obsoleted_by` links, for the obsolete-decision banner. */
  obsoletedByLinks: Readonly<Ref<RecordDetail["inbound_links"]>>;
  /** Inbound `updated_by` links, for the updated-decision banner. */
  updatedByLinks: Readonly<Ref<RecordDetail["inbound_links"]>>;
  /** Inbound links for the sidebar's "Referenced by" card, with
   *  whichever type the lifecycle notice above is currently stating
   *  removed, so the same fact is never shown twice (P11-R-21). An
   *  `updated_by` entry still appears here when `status` is
   *  `"obsoleted"` (obsoleted takes priority in the banner), since
   *  the banner never mentions it in that case. */
  sidebarInboundLinks: Readonly<Ref<RecordDetail["inbound_links"]>>;
  /** Whether the Diff card has any other revision to compare
   *  against; it is hidden otherwise (R-08). */
  showDiff: Readonly<Ref<boolean>>;
}

/**
 * Derive every view-model value `RecordView.vue` needs from the
 * loaded record detail.
 *
 * :param detail: The currently loaded record, or `null` while
 *     loading/erroring.
 * :returns: The computed view-model, reactive to `detail`.
 */
export function useRecordDetailView(
  detail: Ref<RecordDetail | null>,
): RecordDetailView {
  const issueCounts = computed(() =>
    detail.value
      ? {
          error: detail.value.issues.filter((i) => i.severity === "error").length,
          warning: detail.value.issues.filter((i) => i.severity === "warning")
            .length,
        }
      : { error: 0, warning: 0 },
  );

  const issueIndicator = computed(() =>
    detail.value ? issueIndicatorLabel(issueCounts.value) : null,
  );

  /** `null` for published (the chip-visibility rule, R-05: a status
   *  chip is shown only when it differs from the default). */
  const recordKindLabel = computed(() =>
    detail.value && detail.value.metadata.kind === "candidate"
      ? recordStateLabel(detail.value.metadata.kind, detail.value.provenance.ref)
      : null,
  );

  /** Decision/erratum chip, distinct from `recordKindLabel` above
   *  (published/candidate). `null` for a plain decision -- the
   *  default record kind, already shown in the sidebar's Metadata
   *  card (R-05). */
  const recordTypeLabel = computed(() =>
    detail.value && detail.value.metadata.record_kind === "erratum"
      ? recordKindTypeLabel(detail.value.metadata.record_kind)
      : null,
  );

  /** A clear sentence distinguishing a candidate (and its branch) from
   *  a published record (SPEC.md "UI requirements": distinguish
   *  candidate from published everywhere). */
  const provenanceSentence = computed(() =>
    detail.value
      ? provenanceText(detail.value.metadata.kind, detail.value.provenance)
      : "",
  );

  const errataLinkText = computed(() =>
    detail.value ? errataHeaderLinkText(detail.value.errata_summary) : null,
  );

  /** The stale/failed freshness banner's text, or `null` when no
   *  banner should show (candidate, push-only registration, or fresh
   *  content -- see `utils/freshness.ts`). */
  const freshnessBanner = computed(() =>
    detail.value
      ? freshnessBannerText(
          detail.value.metadata.kind,
          detail.value.provenance,
          detail.value.freshness,
        )
      : null,
  );

  /** Shown for an accepted candidate of either kind: acceptance
   *  already guides implementation before publication for a
   *  decision (SPEC.md "Independent approval and sign-off workflow"),
   *  or means "verified, pending publication" for an erratum. */
  const showAcceptedCandidateNote = computed(
    () =>
      detail.value?.metadata.kind === "candidate" &&
      detail.value?.approval.state === "accepted",
  );

  const pageTitle = computed(() => {
    if (!detail.value) {
      return "";
    }
    const { metadata, erratum_for: erratumFor } = detail.value;
    if (metadata.record_kind === "erratum" && erratumFor?.resolved && erratumFor.title) {
      return `Erratum for ${erratumFor.title}`;
    }
    return metadata.title;
  });

  /** Only shown alongside the resolved-erratum title above: an
   *  unresolved erratum, or an ordinary decision, has no subtitle. */
  const pageSubtitle = computed(() => {
    if (!detail.value) {
      return null;
    }
    const { metadata, erratum, erratum_for: erratumFor } = detail.value;
    if (metadata.record_kind !== "erratum" || !erratumFor?.resolved) {
      return null;
    }
    return erratum?.section ? `Section: ${erratum.section}` : null;
  });

  const obsoletedByLinks = computed(() =>
    detail.value
      ? detail.value.inbound_links.filter((link) => link.link_type === "obsoleted_by")
      : [],
  );

  const updatedByLinks = computed(() =>
    detail.value
      ? detail.value.inbound_links.filter((link) => link.link_type === "updated_by")
      : [],
  );

  /** The link type the lifecycle notice currently states, matching
   *  `RecordStatusBanners`' own priority (obsoleted over updated),
   *  or `null` when no notice shows. */
  const sidebarInboundLinks = computed(() => {
    if (!detail.value) {
      return [];
    }
    const statedType =
      detail.value.status === "obsoleted"
        ? "obsoleted_by"
        : detail.value.status === "updated"
          ? "updated_by"
          : null;
    return detail.value.inbound_links.filter(
      (link) => link.link_type !== statedType,
    );
  });

  const showDiff = computed(() => {
    if (!detail.value) {
      return false;
    }
    const { metadata, approval, siblings } = detail.value;
    return hasComparableRevision({
      current: metadata.digest,
      previous: metadata.previous_digest,
      history: approval.history.map((event) => event.digest),
      others: [
        ...siblings.map((sibling) => sibling.digest),
        ...approval.competing_candidates.map((c) => c.digest),
      ],
    });
  });

  return {
    issueCounts,
    issueIndicator,
    recordKindLabel,
    recordTypeLabel,
    provenanceSentence,
    errataLinkText,
    freshnessBanner,
    showAcceptedCandidateNote,
    pageTitle,
    pageSubtitle,
    obsoletedByLinks,
    updatedByLinks,
    sidebarInboundLinks,
    showDiff,
  };
}
