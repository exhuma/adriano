<script setup lang="ts">
/**
 * Record detail page: rendered decision, metadata, validation issues,
 * provenance/freshness, relationships, legacy sign-off, and the
 * read-only approval state.
 *
 * Accept/reject actions and the diff panel arrive in phase 07; this
 * view only displays what `GET /api/v1/records/{id}` returns today.
 */
import { computed, ref, watch } from "vue";

import { ApiError } from "@/api";
import { getRecord } from "@/api/records";
import ErrorState from "@/components/ErrorState.vue";
import LoadingState from "@/components/LoadingState.vue";
import StatusChip from "@/components/StatusChip.vue";
import { withLoading } from "@/composables/useLoading";
import type { RecordDetail } from "@/types/records";
import { formatDate, formatDateTime, formatRelativeTime } from "@/utils/dates";
import {
  approvalStateLabel,
  displayStatusLabel,
  issueIndicatorLabel,
} from "@/utils/labels";

const props = defineProps<{
  /** Record id from the route (`/records/:id`). */
  id: string;
}>();

type LoadState = "loading" | "loaded" | "not-found" | "error";

const loadState = ref<LoadState>("loading");
const errorText = ref<string | null>(null);
const detail = ref<RecordDetail | null>(null);
const copied = ref(false);

function describeError(error: unknown): string {
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
    errorText.value = describeError(error);
    loadState.value = "error";
  }
}

watch(() => props.id, load, { immediate: true });

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

const approvalLabel = computed(() =>
  detail.value
    ? approvalStateLabel(detail.value.approval.state, detail.value.metadata.kind)
    : null,
);

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

const policySummaryText = computed(() => {
  const policy = detail.value?.approval.policy;
  if (!policy) {
    return "";
  }
  if (policy.status === "missing") {
    return "No approval policy is configured; decisions are blocked until one is.";
  }
  if (policy.status === "invalid") {
    return "The configured approval policy is invalid; decisions are blocked until it is fixed.";
  }
  return `Policy "${policy.id}" (version ${policy.version}) — approval is ` +
    `${policy.required ? "required" : "not required"} for this catalog.`;
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
      title="Couldn't load this record"
      :text="errorText ?? undefined"
      @retry="load"
    />

    <template v-else-if="detail">
      <header class="record-header">
        <h1 id="record-heading" class="text-h5">{{ detail.metadata.title }}</h1>
        <div class="record-header-chips">
          <StatusChip v-if="statusLabel" v-bind="statusLabel" />
          <StatusChip v-if="issueIndicator" v-bind="issueIndicator" />
        </div>
      </header>

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

      <v-card class="mb-4" variant="outlined">
        <v-card-title class="text-subtitle-1">Approval</v-card-title>
        <v-card-text>
          <StatusChip v-if="approvalLabel" v-bind="approvalLabel" class="mb-2" />
          <p class="text-body-2">{{ policySummaryText }}</p>
        </v-card-text>
        <v-table v-if="detail.approval.history.length > 0" density="compact">
          <thead>
            <tr>
              <th scope="col">Date</th>
              <th scope="col">Action</th>
              <th scope="col">Reviewer</th>
              <th scope="col">Comment</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="event in detail.approval.history" :key="event.id">
              <td>{{ formatDateTime(event.created_at) }}</td>
              <td>
                <v-icon
                  :icon="event.action === 'accepted' ? 'mdi-check-circle' : 'mdi-close-circle'"
                  :color="event.action === 'accepted' ? 'success' : 'error'"
                  size="small"
                  aria-hidden="true"
                />
                {{ event.action === "accepted" ? "Accepted" : "Rejected" }}
              </td>
              <td>{{ event.actor_display ?? "Unknown" }}</td>
              <td>{{ event.comment ?? "—" }}</td>
            </tr>
          </tbody>
        </v-table>
        <v-card-text v-else class="text-body-2 text-medium-emphasis">
          No formal decisions recorded yet.
        </v-card-text>
      </v-card>

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
