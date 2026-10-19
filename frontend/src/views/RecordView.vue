<script setup lang="ts">
/**
 * Record detail page: rendered decision, metadata, validation
 * issues, provenance/freshness, relationships, legacy sign-off, and
 * the full approval workflow (state, policy, accept/reject,
 * history, divergence, competing candidates, diff). Loads the
 * record and handles its loading/not-found/forbidden/error states;
 * everything else is composed from `components/record/*`.
 */
import { computed, ref, watch } from "vue";

import { ApiError } from "@/api";
import { getRecord } from "@/api/records";
import { forbiddenText, isForbidden } from "@/utils/apiErrors";
import ApprovalCard from "@/components/ApprovalCard.vue";
import DiffPanel from "@/components/DiffPanel.vue";
import DivergenceBanner from "@/components/DivergenceBanner.vue";
import ErrorState from "@/components/ErrorState.vue";
import LoadingState from "@/components/LoadingState.vue";
import LegacySignoffCard from "@/components/record/LegacySignoffCard.vue";
import RecordDecisionCard from "@/components/record/RecordDecisionCard.vue";
import RecordFreshnessBanner from "@/components/record/RecordFreshnessBanner.vue";
import RecordHeader from "@/components/record/RecordHeader.vue";
import RecordIssuesList from "@/components/record/RecordIssuesList.vue";
import RecordLinksCard from "@/components/record/RecordLinksCard.vue";
import RecordMetadataCard from "@/components/record/RecordMetadataCard.vue";
import RecordProvenanceCard from "@/components/record/RecordProvenanceCard.vue";
import RecordSiblingsCard from "@/components/record/RecordSiblingsCard.vue";
import { withLoading } from "@/composables/useLoading";
import type { DecisionSummaryOut } from "@/types/approval";
import type { RecordDetail } from "@/types/records";
import { freshnessBannerText, provenanceText } from "@/utils/freshness";
import {
  displayStatusLabel,
  issueIndicatorLabel,
  recordStateLabel,
} from "@/utils/labels";

const props = defineProps<{
  /** Record id from the route (`/records/:id`). */
  id: string;
}>();

type LoadState = "loading" | "loaded" | "not-found" | "error";

const loadState = ref<LoadState>("loading");
const errorText = ref<string | null>(null);
const errorTitle = ref("Couldn't load this record");
const detail = ref<RecordDetail | null>(null);
const snackbarText = ref<string | null>(null);
const digestChangedBanner = ref(false);

/** `v-snackbar`'s `v-model` is a boolean; this adapts the single
 *  `snackbarText` message into that shape. */
const snackbarVisible = computed({
  get: () => snackbarText.value !== null,
  set: (value: boolean) => {
    if (!value) {
      snackbarText.value = null;
    }
  },
});

function describeError(error: unknown): string {
  if (isForbidden(error)) {
    return forbiddenText(error);
  }
  if (error instanceof ApiError) {
    return `The record could not be loaded (status ${error.status}). ` +
      "Check your connection and try again.";
  }
  return "The record could not be loaded. Check your connection and try again.";
}

async function load(): Promise<void> {
  loadState.value = "loading";
  errorText.value = null;
  try {
    detail.value = await withLoading(() => getRecord(props.id));
    loadState.value = "loaded";
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      loadState.value = "not-found";
      return;
    }
    errorTitle.value = isForbidden(error) ? "No access" : "Couldn't load this record";
    errorText.value = describeError(error);
    loadState.value = "error";
  }
}

watch(
  () => props.id,
  () => {
    digestChangedBanner.value = false;
    snackbarText.value = null;
    void load();
  },
  { immediate: true },
);

const issueCounts = computed(() =>
  detail.value
    ? {
        error: detail.value.issues.filter((i) => i.severity === "error").length,
        warning: detail.value.issues.filter((i) => i.severity === "warning").length,
      }
    : { error: 0, warning: 0 },
);

const issueIndicator = computed(() =>
  detail.value ? issueIndicatorLabel(issueCounts.value) : null,
);

const statusLabel = computed(() =>
  detail.value ? displayStatusLabel(detail.value.status) : null,
);

const recordKindLabel = computed(() =>
  detail.value ? recordStateLabel(detail.value.metadata.kind, detail.value.provenance.ref) : null,
);

/** A clear sentence distinguishing a candidate (and its branch) from
 *  a published record (SPEC.md "UI requirements": distinguish
 *  candidate from published everywhere). */
const provenanceSentence = computed(() =>
  detail.value
    ? provenanceText(detail.value.metadata.kind, detail.value.provenance)
    : "",
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

/** Shown only for an accepted candidate: acceptance already guides
 *  implementation before publication (SPEC.md "Independent approval
 *  and sign-off workflow"). */
const showAcceptedCandidateNote = computed(
  () =>
    detail.value?.metadata.kind === "candidate" &&
    detail.value?.approval.state === "accepted",
);

async function onDecided(event: DecisionSummaryOut): Promise<void> {
  snackbarText.value =
    event.action === "accepted"
      ? "Decision recorded: accepted."
      : "Decision recorded: rejected.";
  await load();
}

async function onDigestChanged(): Promise<void> {
  digestChangedBanner.value = true;
  await load();
}

const inboundForStatus = computed(() => {
  if (!detail.value) {
    return [];
  }
  const relevant = detail.value.status === "obsoleted" ? "obsoleted_by" : "updated_by";
  return detail.value.inbound_links.filter((link) => link.link_type === relevant);
});
</script>

<template>
  <section aria-labelledby="record-heading">
    <LoadingState v-if="loadState === 'loading'" text="Loading record…" />

    <div v-else-if="loadState === 'not-found'" class="not-found">
      <v-icon icon="mdi-file-question-outline" size="48" color="medium-emphasis" />
      <h1 id="record-heading" class="text-h5 mt-2">Record not found</h1>
      <p class="text-body-2 text-medium-emphasis">
        This record does not exist, or has been removed from the catalog.
      </p>
      <v-btn class="mt-4" color="primary" variant="tonal" to="/">
        Back to search
      </v-btn>
    </div>

    <ErrorState
      v-else-if="loadState === 'error'"
      :title="errorTitle"
      :text="errorText ?? undefined"
      @retry="load"
    />

    <template v-else-if="detail">
      <RecordHeader
        :title="detail.metadata.title"
        :record-kind-label="recordKindLabel"
        :status-label="statusLabel"
        :issue-indicator="issueIndicator"
        :provenance-sentence="provenanceSentence"
        :show-accepted-candidate-note="showAcceptedCandidateNote"
      />

      <v-snackbar v-model="snackbarVisible" timeout="4000">
        {{ snackbarText }}
      </v-snackbar>

      <RecordFreshnessBanner
        :digest-changed="digestChangedBanner"
        :superseded-by="inboundForStatus"
        :freshness-text="freshnessBanner"
        @close-digest-changed="digestChangedBanner = false"
      />

      <RecordIssuesList :issues="detail.issues" />

      <RecordDecisionCard :rendered-html="detail.rendered_html" />

      <RecordMetadataCard
        :adr-uuid="detail.metadata.adr_uuid"
        :decision-date="detail.metadata.decision_date"
        :decision-date-inferred="detail.metadata.decision_date_inferred"
        :record-kind="detail.metadata.record_kind"
      />

      <RecordProvenanceCard :provenance="detail.provenance" :freshness="detail.freshness" />

      <DivergenceBanner
        :divergence="detail.approval.divergence"
        :competing-candidates="detail.approval.competing_candidates"
      />

      <ApprovalCard
        :approval="detail.approval"
        :record-kind="detail.metadata.kind"
        :record-id="props.id"
        @decided="onDecided"
        @digest-changed="onDigestChanged"
      />

      <DiffPanel
        :record-id="props.id"
        :current-digest="detail.metadata.digest"
        :previous-digest="detail.metadata.previous_digest"
        :source-id="detail.provenance.source_id"
        :project="detail.provenance.project"
        :ref-name="detail.provenance.ref"
        :last-indexed-at="detail.freshness.last_success_at"
        :history="detail.approval.history"
        :siblings="detail.siblings"
        :competing-candidates="detail.approval.competing_candidates"
      />

      <LegacySignoffCard :entries="detail.legacy_signoff_unverified" />

      <RecordLinksCard
        :outbound-links="detail.outbound_links"
        :inbound-links="detail.inbound_links"
        :errata="detail.errata"
      />

      <RecordSiblingsCard :siblings="detail.siblings" />
    </template>
  </section>
</template>

<style scoped>
.not-found {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 3rem 1rem;
  text-align: center;
}
</style>
