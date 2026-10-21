<script setup lang="ts">
/**
 * Record detail page: a full-width header and status banners, then
 * two columns -- the document body and approval workflow as the main
 * column, and identity/provenance/relationships/legacy sign-off in a
 * sidebar (rfc-editor.org/info layout: status prominent at the top,
 * metadata to the side, no tabs). Loads the record and handles its
 * loading/not-found/forbidden/error states; the view-model computeds
 * (titles, chips, banners) live in `useRecordDetailView`, and
 * everything else is composed from `components/record/*`. After a
 * decision or a digest-changed refresh, the record is re-fetched in
 * place (P11-R-16): the loaded content stays mounted (only the app
 * bar's `v-progress-linear`, via `useLoading`, signals the fetch) so
 * focus and scroll position are never reset the way they were when
 * that refresh swapped in the `loading` state and unmounted the
 * page; a request counter discards a stale response if a newer
 * refresh or route change started first. Once the refreshed detail
 * is in, focus moves to the sidebar's status heading (a `tabindex=
 * -1` target, `RecordApprovalSummaryCard`'s `h2`) so a screen-reader
 * user lands on the outcome instead of keeping focus on a button
 * that may have gone away (e.g. Accept/Reject hidden once decided);
 * the outcome itself is announced through the existing snackbar
 * (decisions) or the existing "content changed" alert (digest
 * changes), both already live regions.
 */
import { computed, nextTick, ref, watch } from "vue";

import { ApiError } from "@/api";
import { getRecord } from "@/api/records";
import { isForbidden } from "@/utils/apiErrors";
import ApprovalCard from "@/components/ApprovalCard.vue";
import DiffPanel from "@/components/DiffPanel.vue";
import DivergenceBanner from "@/components/DivergenceBanner.vue";
import ErrorState from "@/components/ErrorState.vue";
import LoadingState from "@/components/LoadingState.vue";
import ErrataSection from "@/components/record/ErrataSection.vue";
import ErratumBody from "@/components/record/ErratumBody.vue";
import RecordDecisionCard from "@/components/record/RecordDecisionCard.vue";
import RecordFreshnessBanner from "@/components/record/RecordFreshnessBanner.vue";
import RecordHeader from "@/components/record/RecordHeader.vue";
import RecordIssuesList from "@/components/record/RecordIssuesList.vue";
import RecordSidebar from "@/components/record/RecordSidebar.vue";
import RecordStatusBanners from "@/components/record/RecordStatusBanners.vue";
import {
  decidedSnackbarText,
  describeRecordLoadError,
  useRecordDetailView,
} from "@/composables/useRecordDetailView";
import { withLoading } from "@/composables/useLoading";
import type { DecisionSummaryOut } from "@/types/approval";
import type { RecordDetail } from "@/types/records";

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

/** Identifies the most recent `getRecord` request (initial load,
 *  route change, or post-decision refresh); a response is applied
 *  only when it is still the latest one requested (P11-R-16). */
const requestId = ref(0);

const {
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
} = useRecordDetailView(detail);

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

/** Full page load: used for the first mount and whenever the route's
 *  `id` changes, so it owns `loadState` (loading/not-found/error
 *  states replace the page). */
async function load(): Promise<void> {
  const currentRequest = ++requestId.value;
  loadState.value = "loading";
  errorText.value = null;
  try {
    const nextDetail = await withLoading(() => getRecord(props.id));
    if (currentRequest !== requestId.value) {
      return; // Superseded by a newer request; discard (P11-R-16).
    }
    detail.value = nextDetail;
    loadState.value = "loaded";
  } catch (error) {
    if (currentRequest !== requestId.value) {
      return;
    }
    if (error instanceof ApiError && error.status === 404) {
      loadState.value = "not-found";
      return;
    }
    errorTitle.value = isForbidden(error) ? "No access" : "Couldn't load this record";
    errorText.value = describeRecordLoadError(error);
    loadState.value = "error";
  }
}

/**
 * Re-fetch the record after a decision or a digest-changed conflict
 * without unmounting the already-loaded page (P11-R-16): `loadState`
 * stays `"loaded"` throughout, so the main/sidebar content, scroll
 * position and focus are undisturbed; `useLoading`'s app-bar
 * progress bar is the only loading feedback. A stale response (an
 * even newer refresh, or a route change to a different record) is
 * discarded rather than overwriting fresher data. On error, the
 * still-valid content on screen is kept and the error is reported
 * through the snackbar instead (preserve work on error).
 */
async function refreshInPlace(): Promise<void> {
  const currentRequest = ++requestId.value;
  try {
    const nextDetail = await withLoading(() => getRecord(props.id));
    if (currentRequest !== requestId.value) {
      return;
    }
    detail.value = nextDetail;
  } catch (error) {
    if (currentRequest !== requestId.value) {
      return;
    }
    snackbarText.value = describeRecordLoadError(error);
  }
}

/** Move focus to the sidebar's status heading once the refreshed
 *  detail has rendered, so a screen-reader user lands on the
 *  outcome rather than on a control that may no longer exist
 *  (P11-R-16). The heading is a `tabindex="-1"` target solely for
 *  this programmatic focus; it is never a tab stop. */
async function focusSidebarHeading(): Promise<void> {
  await nextTick();
  document.getElementById("sidebar-heading")?.focus();
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

async function onDecided(event: DecisionSummaryOut): Promise<void> {
  const isErratum = detail.value?.metadata.record_kind === "erratum";
  snackbarText.value = decidedSnackbarText(event.action, isErratum);
  await refreshInPlace();
  await focusSidebarHeading();
}

async function onDigestChanged(): Promise<void> {
  digestChangedBanner.value = true;
  await refreshInPlace();
  await focusSidebarHeading();
}
</script>

<template>
  <section aria-labelledby="record-heading">
    <LoadingState v-if="loadState === 'loading'" text="Loading record…" />

    <div
      v-else-if="loadState === 'not-found'"
      class="d-flex flex-column align-center text-center py-12 px-4"
    >
      <v-icon
        icon="mdi-file-question-outline"
        size="48"
        color="medium-emphasis"
        aria-hidden="true"
      />
      <h1
        id="record-heading"
        class="text-headline-medium font-weight-medium mt-2"
      >
        Record not found
      </h1>
      <p class="text-body-medium text-medium-emphasis">
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
        :title="pageTitle"
        :subtitle="pageSubtitle"
        :record-kind="detail.metadata.record_kind"
        :record-kind-label="recordKindLabel"
        :record-type-label="recordTypeLabel"
        :issue-indicator="issueIndicator"
        :provenance-sentence="provenanceSentence"
        :errata-link-text="errataLinkText"
        :show-accepted-candidate-note="showAcceptedCandidateNote"
      />

      <v-snackbar v-model="snackbarVisible" timeout="4000">
        {{ snackbarText }}
      </v-snackbar>

      <RecordStatusBanners
        :status="detail.status"
        :obsoleted-by="obsoletedByLinks"
        :updated-by="updatedByLinks"
        :erratum-for="detail.erratum_for"
      />

      <RecordFreshnessBanner
        :digest-changed="digestChangedBanner"
        :freshness-text="freshnessBanner"
        @close-digest-changed="digestChangedBanner = false"
      />

      <v-row>
        <v-col cols="12" md="8">
          <RecordIssuesList :issues="detail.issues" />

          <RecordDecisionCard
            v-if="detail.metadata.record_kind === 'decision'"
            :rendered-html="detail.rendered_html"
            :title="detail.metadata.title"
          />
          <ErratumBody
            v-else
            :erratum="detail.erratum"
            :erratum-for="detail.erratum_for"
          />

          <ErrataSection :errata="detail.errata" />

          <DivergenceBanner
            :divergence="detail.approval.divergence"
            :competing-candidates="detail.approval.competing_candidates"
            :record-kind="detail.metadata.record_kind"
          />

          <ApprovalCard
            id="approval"
            :approval="detail.approval"
            :kind="detail.metadata.kind"
            :record-kind="detail.metadata.record_kind"
            :record-id="props.id"
            :record-title="pageTitle"
            :record-ref="detail.provenance.ref"
            :has-validation-issues="detail.issues.length > 0"
            @decided="onDecided"
            @digest-changed="onDigestChanged"
          />

          <DiffPanel
            v-if="showDiff"
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
        </v-col>

        <v-col cols="12" md="4">
          <RecordSidebar
            :record-kind="detail.metadata.record_kind"
            :kind="detail.metadata.kind"
            :record-id="props.id"
            :record-title="pageTitle"
            :approval="detail.approval"
            :adr-uuid="detail.metadata.adr_uuid"
            :decision-date="detail.metadata.decision_date"
            :decision-date-inferred="detail.metadata.decision_date_inferred"
            :provenance="detail.provenance"
            :freshness="detail.freshness"
            :outbound-links="detail.outbound_links"
            :inbound-links="sidebarInboundLinks"
            :siblings="detail.siblings"
            :legacy-signoff-entries="detail.legacy_signoff_unverified"
            @decided="onDecided"
            @digest-changed="onDigestChanged"
          />
        </v-col>
      </v-row>
    </template>
  </section>
</template>

