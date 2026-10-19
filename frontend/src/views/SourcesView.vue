<script setup lang="ts">
/**
 * Source registration status page: per-registration configuration,
 * freshness, and recovery hints for operators.
 *
 * Operator-triggered polling ("Poll now") arrives in phase 06 once
 * authorization is wired up; this view is read-only.
 */
import { computed, onMounted, ref, shallowRef } from "vue";

import { ApiError } from "@/api";
import { listSources } from "@/api/sources";
import ErrorState from "@/components/ErrorState.vue";
import LoadingState from "@/components/LoadingState.vue";
import StatusChip from "@/components/StatusChip.vue";
import { withLoading } from "@/composables/useLoading";
import type { SourceOut } from "@/types/sources";
import { formatDateTime, formatRelativeTime } from "@/utils/dates";
import { pollStatusLabel, type StatusLabel } from "@/utils/labels";

type LoadState = "loading" | "loaded" | "error";

const loadState = ref<LoadState>("loading");
const errorText = ref<string | null>(null);
// `shallowRef`, not `ref`: the whole array is always replaced
// wholesale on load, never mutated in place, and `SourceOut.last_error`
// is the backend's recursive `JsonValue` type -- Vue's deep
// `UnwrapRef` mapped type recurses into it and TypeScript gives up
// with "Type instantiation is excessively deep" (TS2589).
const sources = shallowRef<SourceOut[]>([]);

/** Pre-resolved view data for one registration row. */
interface SourceRow {
  id: string;
  type: string;
  intake: string;
  publishedRef: string;
  enabled: boolean;
  statusLabel: StatusLabel;
  lastAttempt: { relative: string; absolute: string } | null;
  lastSuccess: { relative: string; absolute: string } | null;
  problem: string | null;
  hint: string | null;
}

function describeError(error: unknown): string {
  if (error instanceof ApiError) {
    return `Source status could not be loaded (status ${error.status}). ` +
      "Check your connection and try again.";
  }
  return "Source status could not be loaded. Check your connection and try again.";
}

async function load(): Promise<void> {
  loadState.value = "loading";
  errorText.value = null;
  try {
    sources.value = await withLoading(() => listSources());
    loadState.value = "loaded";
  } catch (error) {
    errorText.value = describeError(error);
    loadState.value = "error";
  }
}

onMounted(load);

/** A human-readable problem summary, or `null` when there is none. */
function problemSummary(source: SourceOut): string | null {
  if (source.config_error) {
    return source.config_error;
  }
  const lastError: unknown = source.last_error;
  if (typeof lastError === "string") {
    return lastError;
  }
  if (lastError !== null && lastError !== undefined) {
    return JSON.stringify(lastError);
  }
  return null;
}

/** A concrete next step for the operator, or `null` when healthy. */
function recoveryHint(source: SourceOut, problem: string | null): string | null {
  if (!problem && source.last_status !== "failed" && source.last_status !== "partial") {
    return null;
  }
  return source.type === "gitlab"
    ? "Check the token env var, base_url, and scope in catalog.yaml, then poll again."
    : "Check the root path and scope in catalog.yaml, then poll again.";
}

/** Resolve the display-ready fields for one registration row once,
 *  so the template never re-derives them (and never has to narrow
 *  the recursive `JsonValue` type of `last_error` itself). */
function toRow(source: SourceOut): SourceRow {
  const problem = problemSummary(source);
  return {
    id: source.id,
    type: source.type,
    intake: source.intake.join(", "),
    publishedRef: source.published_ref,
    enabled: source.enabled,
    statusLabel: pollStatusLabel(source.last_status, source.stale),
    lastAttempt: source.last_attempt_at
      ? {
          relative: formatRelativeTime(source.last_attempt_at) ?? "",
          absolute: formatDateTime(source.last_attempt_at) ?? "",
        }
      : null,
    lastSuccess: source.last_success_at
      ? {
          relative: formatRelativeTime(source.last_success_at) ?? "",
          absolute: formatDateTime(source.last_success_at) ?? "",
        }
      : null,
    problem,
    hint: recoveryHint(source, problem),
  };
}

const rows = computed<SourceRow[]>(() => sources.value.map(toRow));
</script>

<template>
  <section aria-labelledby="sources-heading">
    <h1 id="sources-heading" class="text-h5 mb-4">Sources</h1>

    <LoadingState v-if="loadState === 'loading'" text="Loading source status…" />

    <ErrorState
      v-else-if="loadState === 'error'"
      title="Couldn't load source status"
      :text="errorText ?? undefined"
      @retry="load"
    />

    <template v-else>
      <v-table v-if="rows.length > 0">
        <thead>
          <tr>
            <th scope="col">Registration</th>
            <th scope="col">Type</th>
            <th scope="col">Intake</th>
            <th scope="col">Published ref</th>
            <th scope="col">Status</th>
            <th scope="col">Last attempt</th>
            <th scope="col">Last success</th>
            <th scope="col">Problem &amp; recovery</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.id">
            <th scope="row">{{ row.id }}</th>
            <td>{{ row.type }}</td>
            <td>{{ row.intake }}</td>
            <td>{{ row.publishedRef }}</td>
            <td>
              <StatusChip v-bind="row.statusLabel" />
              <span v-if="!row.enabled" class="ml-2">
                <StatusChip icon="mdi-pause-circle-outline" text="Disabled" />
              </span>
            </td>
            <td>
              <span v-if="row.lastAttempt">
                {{ row.lastAttempt.relative }}
                <br>
                <span class="text-caption text-medium-emphasis">
                  {{ row.lastAttempt.absolute }}
                </span>
              </span>
              <span v-else>Never</span>
            </td>
            <td>
              <span v-if="row.lastSuccess">
                {{ row.lastSuccess.relative }}
                <br>
                <span class="text-caption text-medium-emphasis">
                  {{ row.lastSuccess.absolute }}
                </span>
              </span>
              <span v-else>Never</span>
            </td>
            <td>
              <template v-if="row.problem || row.hint">
                <p v-if="row.problem" class="text-body-2">{{ row.problem }}</p>
                <p v-if="row.hint" class="text-body-2 text-medium-emphasis">
                  {{ row.hint }}
                </p>
              </template>
              <span v-else class="text-medium-emphasis">—</span>
            </td>
          </tr>
        </tbody>
      </v-table>

      <p v-else class="text-body-2 text-medium-emphasis">
        No source registrations are configured yet.
      </p>
    </template>
  </section>
</template>
