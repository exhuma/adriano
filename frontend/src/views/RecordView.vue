<script setup lang="ts">
/**
 * Record detail page: rendered decision, metadata, validation
 * issues, provenance/freshness, relationships, legacy sign-off, and
 * the full approval workflow (state, policy, accept/reject,
 * history, divergence, competing candidates, diff).
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
import StatusChip from "@/components/StatusChip.vue";
import { withLoading } from "@/composables/useLoading";
import type { DecisionSummaryOut } from "@/types/approval";
import type { RecordDetail } from "@/types/records";
import { formatDate, formatDateTime, formatRelativeTime } from "@/utils/dates";
import {
  approvalStateLabel,
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
const copied = ref(false);
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
const provenanceText = computed(() => {
  if (!detail.value) {
    return "";
  }
  const { metadata, provenance } = detail.value;
  if (metadata.kind === "candidate") {
    return `Candidate from branch ${provenance.ref} (${provenance.source_id} / ${provenance.project}).`;
  }
  return `Published from ${provenance.source_id} / ${provenance.project}.`;
});

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

const decisionDateText = computed(() => formatDate(detail.value?.metadata.decision_date));

const sourceUrlIsLink = computed(() => {
  const url = detail.value?.provenance.source_url;
  return Boolean(url && /^https?:\/\//.test(url));
});

async function copyUuid(): Promise<void> {
  const value = detail.value?.metadata.adr_uuid;
  if (!value) {
    return;
  }
  try {
    await navigator.clipboard.writeText(value);
    copied.value = true;
    setTimeout(() => {
      copied.value = false;
    }, 2000);
  } catch {
    // Clipboard API unavailable (e.g. insecure context); the UUID is
    // already visible as selectable text, so this is a soft failure.
  }
}

function linkTypeLabel(type: string): string {
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
      <header class="record-header">
        <h1 id="record-heading" class="text-h5">{{ detail.metadata.title }}</h1>
        <div class="record-header-chips">
          <StatusChip v-if="recordKindLabel" v-bind="recordKindLabel" />
          <StatusChip v-if="statusLabel" v-bind="statusLabel" />
          <StatusChip v-if="issueIndicator" v-bind="issueIndicator" />
        </div>
      </header>

      <p class="text-body-2 text-medium-emphasis mb-2">{{ provenanceText }}</p>

      <p v-if="showAcceptedCandidateNote" class="text-body-2 mb-4">
        <v-icon icon="mdi-check-decagram" color="success" size="small" aria-hidden="true" />
        Accepted — this candidate is authoritative for implementation before
        publication.
      </p>

      <v-alert
        v-if="digestChangedBanner"
        type="warning"
        variant="tonal"
        icon="mdi-refresh-alert"
        closable
        class="mb-4"
        @click:close="digestChangedBanner = false"
      >
        The content changed while you were reviewing; review the new
        revision before deciding.
      </v-alert>

      <v-snackbar v-model="snackbarVisible" timeout="4000">
        {{ snackbarText }}
      </v-snackbar>

      <p v-if="inboundForStatus.length > 0" class="text-body-2 mb-4">
        {{ linkTypeLabel(inboundForStatus[0].link_type) }}:
        <router-link
          v-for="(link, index) in inboundForStatus"
          :key="link.source_id"
          :to="`/records/${link.source_id}`"
        >
          {{ link.source_title }}<span v-if="index < inboundForStatus.length - 1">, </span>
        </router-link>
      </p>

      <v-alert
        v-if="detail.freshness.stale"
        type="warning"
        variant="tonal"
        icon="mdi-clock-alert-outline"
        class="mb-4"
      >
        Last indexed
        {{ formatRelativeTime(detail.freshness.last_success_at) ?? "never" }} —
        the source could not be refreshed, so this may not be the current
        published revision.
      </v-alert>

      <v-card v-if="detail.issues.length > 0" class="mb-4" variant="outlined">
        <v-card-title class="text-subtitle-1">Validation issues</v-card-title>
        <v-list density="compact">
          <v-list-item v-for="(issue, index) in detail.issues" :key="index">
            <template #prepend>
              <v-icon
                :icon="issue.severity === 'error' ? 'mdi-alert-circle' : 'mdi-alert'"
                :color="issue.severity === 'error' ? 'error' : 'warning'"
                aria-hidden="true"
              />
            </template>
            <v-list-item-title>
              <span class="sr-only">{{ issue.severity }}: </span>{{ issue.message }}
            </v-list-item-title>
          </v-list-item>
        </v-list>
      </v-card>

      <v-card class="mb-4" variant="outlined">
        <v-card-title class="text-subtitle-1">Decision record</v-card-title>
        <v-card-text>
          <!--
            `rendered_html` is sanitized server-side at ingest time
            with `nh3` before storage (see DECISIONS.md "Record
            schema"). It is the only place this app uses `v-html`.
          -->
          <!-- eslint-disable-next-line vue/no-v-html -->
          <div class="rendered-markdown" v-html="detail.rendered_html" />
        </v-card-text>
      </v-card>

      <v-card class="mb-4" variant="outlined">
        <v-card-title class="text-subtitle-1">Metadata</v-card-title>
        <v-list density="compact">
          <v-list-item>
            <v-list-item-title>UUID</v-list-item-title>
            <v-list-item-subtitle>
              <span v-if="detail.metadata.adr_uuid">
                <code>{{ detail.metadata.adr_uuid }}</code>
                <v-btn
                  icon="mdi-content-copy"
                  size="x-small"
                  variant="text"
                  :aria-label="copied ? 'Copied UUID to clipboard' : 'Copy UUID to clipboard'"
                  @click="copyUuid"
                />
                <span v-if="copied" class="text-success">Copied!</span>
              </span>
              <span v-else>Not available (no valid UUID in this file)</span>
            </v-list-item-subtitle>
          </v-list-item>
          <v-list-item>
            <v-list-item-title>Decision date</v-list-item-title>
            <v-list-item-subtitle>
              <span v-if="decisionDateText">
                {{ decisionDateText }}
                <StatusChip
                  v-if="detail.metadata.decision_date_inferred"
                  icon="mdi-information-outline"
                  text="Inferred from filename"
                  class="ml-1"
                />
              </span>
              <span v-else>Not recorded</span>
            </v-list-item-subtitle>
          </v-list-item>
          <v-list-item>
            <v-list-item-title>Kind</v-list-item-title>
            <v-list-item-subtitle>
              {{ detail.metadata.record_kind === "erratum" ? "Erratum" : "Decision" }}
            </v-list-item-subtitle>
          </v-list-item>
        </v-list>
      </v-card>

      <v-card class="mb-4" variant="outlined">
        <v-card-title class="text-subtitle-1">Provenance</v-card-title>
        <v-list density="compact">
          <v-list-item>
            <v-list-item-title>Source</v-list-item-title>
            <v-list-item-subtitle>
              {{ detail.provenance.source_id }} / {{ detail.provenance.project }}
            </v-list-item-subtitle>
          </v-list-item>
          <v-list-item>
            <v-list-item-title>Path &amp; ref</v-list-item-title>
            <v-list-item-subtitle>
              {{ detail.provenance.path }} @ {{ detail.provenance.ref }}
            </v-list-item-subtitle>
          </v-list-item>
          <v-list-item>
            <v-list-item-title>Source location</v-list-item-title>
            <v-list-item-subtitle>
              <a
                v-if="sourceUrlIsLink"
                :href="detail.provenance.source_url!"
                target="_blank"
                rel="noopener"
              >
                View source <v-icon icon="mdi-open-in-new" size="small" aria-hidden="true" />
              </a>
              <span v-else-if="detail.provenance.source_url">
                {{ detail.provenance.source_url }}
              </span>
              <span v-else>Not available</span>
            </v-list-item-subtitle>
          </v-list-item>
          <v-list-item>
            <v-list-item-title>Freshness</v-list-item-title>
            <v-list-item-subtitle>
              Last indexed
              {{ formatRelativeTime(detail.freshness.last_success_at) ?? "never" }}
              <span v-if="detail.freshness.last_success_at">
                ({{ formatDateTime(detail.freshness.last_success_at) }})
              </span>
            </v-list-item-subtitle>
          </v-list-item>
        </v-list>
      </v-card>

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
        :history="detail.approval.history"
        :siblings="detail.siblings"
        :competing-candidates="detail.approval.competing_candidates"
      />

      <v-card
        v-if="detail.legacy_signoff_unverified.length > 0"
        class="mb-4"
        variant="outlined"
      >
        <v-card-title class="text-subtitle-1">Legacy sign-off (unverified)</v-card-title>
        <v-card-text class="text-body-2 text-medium-emphasis">
          These values come from the legacy <code>signed-off-by</code> field in
          the document itself. They are historical, unauthenticated text, not
          a verified approval, and do not satisfy the approval policy.
        </v-card-text>
        <v-list density="compact">
          <v-list-item v-for="(entry, index) in detail.legacy_signoff_unverified" :key="index">
            {{ entry }}
          </v-list-item>
        </v-list>
      </v-card>

      <v-card
        v-if="detail.outbound_links.length > 0"
        class="mb-4"
        variant="outlined"
      >
        <v-card-title class="text-subtitle-1">Related decisions</v-card-title>
        <v-list density="compact">
          <v-list-item v-for="(link, index) in detail.outbound_links" :key="index">
            <v-list-item-title>{{ linkTypeLabel(link.link_type) }}</v-list-item-title>
            <v-list-item-subtitle>
              <router-link v-if="link.target_id" :to="`/records/${link.target_id}`">
                {{ link.target_title ?? link.target_uuid }}
              </router-link>
              <span v-else-if="link.ambiguous" class="text-warning">
                <v-icon icon="mdi-alert" size="small" aria-hidden="true" />
                Ambiguous: matches {{ link.candidate_ids.length }} records
                (uuid {{ link.target_uuid }})
              </span>
              <span v-else class="text-medium-emphasis">
                <v-icon icon="mdi-link-off" size="small" aria-hidden="true" />
                Missing target (uuid {{ link.target_uuid }})
              </span>
            </v-list-item-subtitle>
          </v-list-item>
        </v-list>
      </v-card>

      <v-card
        v-if="detail.inbound_links.length > 0"
        class="mb-4"
        variant="outlined"
      >
        <v-card-title class="text-subtitle-1">Referenced by</v-card-title>
        <v-list density="compact">
          <v-list-item
            v-for="link in detail.inbound_links"
            :key="`${link.link_type}-${link.source_id}`"
          >
            <v-list-item-title>{{ linkTypeLabel(link.link_type) }}</v-list-item-title>
            <v-list-item-subtitle>
              <router-link :to="`/records/${link.source_id}`">
                {{ link.source_title }}
              </router-link>
            </v-list-item-subtitle>
          </v-list-item>
        </v-list>
      </v-card>

      <v-card v-if="detail.errata.length > 0" class="mb-4" variant="outlined">
        <v-card-title class="text-subtitle-1">Errata</v-card-title>
        <v-list density="compact">
          <v-list-item v-for="erratum in detail.errata" :key="erratum.id">
            <router-link :to="`/records/${erratum.id}`">{{ erratum.title }}</router-link>
          </v-list-item>
        </v-list>
      </v-card>

      <v-card v-if="detail.siblings.length > 0" class="mb-4" variant="outlined">
        <v-card-title class="text-subtitle-1">Other revisions</v-card-title>
        <v-list density="compact">
          <v-list-item v-for="sibling in detail.siblings" :key="sibling.id">
            <router-link :to="`/records/${sibling.id}`">
              {{ sibling.title }}
            </router-link>
            <template #append>
              <StatusChip
                v-bind="approvalStateLabel(sibling.approval_state, sibling.kind)"
              />
            </template>
          </v-list-item>
        </v-list>
      </v-card>
    </template>
  </section>
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

.not-found {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 3rem 1rem;
  text-align: center;
}

.rendered-markdown {
  overflow-wrap: break-word;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
}
</style>
