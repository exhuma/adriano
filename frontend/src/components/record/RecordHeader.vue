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
import type { StatusLabel } from "@/utils/labels";

defineProps<{
  /** Record title, shown as the page's `h1`. */
  title: string;
  /** Candidate/published chip, or `null` to hide it. */
  recordKindLabel: StatusLabel | null;
  /** Decision/erratum chip (from `metadata.record_kind`), or `null`
   *  to hide it. */
  recordTypeLabel: StatusLabel | null;
  /** Validation issue-count chip, or `null` when there are none. */
  issueIndicator: StatusLabel | null;
  /** Sentence distinguishing candidate (with branch) from published. */
  provenanceSentence: string;
  /** Whether to show the accepted-candidate authority note. */
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

  <p class="text-body-2 text-medium-emphasis mb-2">{{ provenanceSentence }}</p>

  <p v-if="showAcceptedCandidateNote" class="text-body-2 mb-4">
    <v-icon icon="mdi-check-decagram" color="success" size="small" aria-hidden="true" />
    Accepted — this candidate is authoritative for implementation before
    publication.
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
