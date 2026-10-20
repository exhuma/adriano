<script setup lang="ts">
/**
 * Record detail page header: title, state/kind/issue chips, the
 * provenance sentence distinguishing candidate from published, and
 * the accepted-candidate note. Purely presentational: all labels are
 * computed by the parent view from the loaded record. Obsoleted/
 * updated status moved to the prominent `RecordStatusBanners` below
 * this header (rfc-editor.org/info layout), so it is no longer a
 * small chip here.
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
  /** Candidate/published chip, or `null` to hide it. */
  recordKindLabel: StatusLabel | null;
  /** Decision/erratum chip (from `metadata.record_kind`), or `null`
   *  to hide it. */
  recordTypeLabel: StatusLabel | null;
  /** Validation issue-count chip, or `null` when there are none. */
  issueIndicator: StatusLabel | null;
  /** Sentence distinguishing candidate (with branch) from published. */
  provenanceSentence: string;
  /** Whether to show the accepted-candidate note (a candidate whose
   *  current content was accepted/verified). */
  showAcceptedCandidateNote: boolean;
}>();
</script>

<template>
  <header class="record-header">
    <h1 id="record-heading" class="text-h5">{{ title }}</h1>
    <div class="record-header-chips">
      <StatusChip v-if="recordKindLabel" v-bind="recordKindLabel" />
      <StatusChip v-if="recordTypeLabel" v-bind="recordTypeLabel" />
      <StatusChip v-if="issueIndicator" v-bind="issueIndicator" />
    </div>
  </header>

  <p v-if="subtitle" class="text-body-2 text-medium-emphasis mb-1">
    {{ subtitle }}
  </p>

  <p class="text-body-2 text-medium-emphasis mb-2">{{ provenanceSentence }}</p>

  <p v-if="showAcceptedCandidateNote" class="text-body-2 mb-4">
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

<style scoped>
.record-header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.5rem;
}

.record-header-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.375rem;
}
</style>
