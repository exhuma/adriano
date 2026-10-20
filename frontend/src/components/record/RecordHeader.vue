<script setup lang="ts">
/**
 * Record detail page header: title, state/kind/issue chips, the
 * provenance sentence distinguishing candidate from published (with
 * an inline errata link, R-04: the old full-sentence "has errata"
 * banner is now a short link here instead), and the accepted-
 * candidate note. Purely presentational: all labels are computed by
 * the parent view from the loaded record. Obsoleted/updated status
 * lives in the single lifecycle notice in `RecordStatusBanners`
 * below this header (rfc-editor.org/info layout), not here. Chips
 * are shown exactly as given: the caller only passes a non-`null`
 * `recordKindLabel`/`recordTypeLabel` for a non-default state (R-05 --
 * "Published" and "Decision" add nothing: published is the default
 * lifecycle state, and the kind already shows in the sidebar).
 */
import StatusChip from "@/components/StatusChip.vue";
import type { RecordKind } from "@/types/records";
import type { StatusLabel } from "@/utils/labels";

defineProps<{
  /** Record title, shown as the page's `h1`. For a resolved erratum
   *  this is "Erratum for <target title>", computed by the caller
   *  (`useRecordDetailView`), not the erratum's own stored title. */
  title: string;
  /** Subtitle line under the `h1`, e.g. the erratum's section, or
   *  `null` to hide it. */
  subtitle?: string | null;
  /** Whether the viewed record is a normal decision or an erratum;
   *  picks the accepted-candidate note's wording. */
  recordKind: RecordKind;
  /** Candidate chip, or `null` to hide it (published is the default
   *  lifecycle state, never shown as a chip, R-05). */
  recordKindLabel: StatusLabel | null;
  /** Erratum chip, or `null` to hide it (decision is the default
   *  record kind, already shown in the sidebar's Metadata card, so
   *  it is never shown as a chip, R-05). */
  recordTypeLabel: StatusLabel | null;
  /** Validation issue-count chip, or `null` when there are none. */
  issueIndicator: StatusLabel | null;
  /** Sentence distinguishing candidate (with branch) from published. */
  provenanceSentence: string;
  /** "N erratum(s)"/"N proposed errata" link text appended to the
   *  metadata line as "… · <text> · View errata", or `null`/omitted
   *  to hide it when the decision has no errata at all (R-04). */
  errataLinkText?: string | null;
  /** Whether to show the accepted-candidate note (works for both a
   *  decision and an erratum; this component picks the wording). */
  showAcceptedCandidateNote: boolean;
}>();
</script>

<template>
  <header class="record-header d-flex flex-wrap align-center ga-3 mb-2">
    <h1
      id="record-heading"
      class="text-headline-medium font-weight-medium mb-0"
    >
      {{ title }}
    </h1>
    <div class="d-flex flex-wrap align-center ga-2">
      <StatusChip v-if="recordKindLabel" v-bind="recordKindLabel" />
      <StatusChip v-if="recordTypeLabel" v-bind="recordTypeLabel" />
      <StatusChip v-if="issueIndicator" v-bind="issueIndicator" />
    </div>
  </header>

  <p v-if="subtitle" class="text-body-medium text-medium-emphasis mt-0 mb-1">
    {{ subtitle }}
  </p>

  <p class="text-body-medium text-medium-emphasis mt-0 mb-2">
    {{ provenanceSentence }}
    <template v-if="errataLinkText">
      · {{ errataLinkText }} · <a href="#errata">View errata</a>
    </template>
  </p>

  <p v-if="showAcceptedCandidateNote" class="text-body-medium mt-0 mb-4">
    <v-icon icon="mdi-check-decagram" color="success" size="small" aria-hidden="true" />
    <template v-if="recordKind === 'erratum'">
      Verified — this correction applies once published.
    </template>
    <template v-else>
      Accepted — this candidate is authoritative for implementation before
      publication.
    </template>
  </p>
</template>
