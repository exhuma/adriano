<script setup lang="ts">
/**
 * Source registration status page: per-registration configuration,
 * freshness, and recovery hints, plus operator-triggered polling.
 *
 * "Poll all" and per-row "Poll now" are shown only to callers with
 * the `operate` permission (`useAuth().can("operate")`); everyone
 * else sees a short note naming who can poll instead of a disabled,
 * unexplained control (module-ux-principles "Write recovery messages
 * for humans").
 */
import { computed, onMounted, onUnmounted, ref, shallowRef } from "vue";

import { ApiError } from "@/api";
import { listSources, pollAllSources, pollSource } from "@/api/sources";
import ErrorState from "@/components/ErrorState.vue";
import LoadingState from "@/components/LoadingState.vue";
import SourceProblemCell from "@/components/SourceProblemCell.vue";
import StatusChip from "@/components/StatusChip.vue";
import { useAuth } from "@/composables/useAuth";
import { withLoading } from "@/composables/useLoading";
import type { SourceOut } from "@/types/sources";
import { formatDateTime, formatRelativeTime } from "@/utils/dates";
import { errorDetail, forbiddenText, isForbidden } from "@/utils/apiErrors";
import { pollStatusLabel, type StatusLabel } from "@/utils/labels";
import { describeLastError, type SourceProblemDisplay } from "@/utils/sourceErrors";

type LoadState = "loading" | "loaded" | "error";

const { can } = useAuth();
const canOperate = computed(() => can("operate"));

const loadState = ref<LoadState>("loading");
const errorText = ref<string | null>(null);
const errorTitle = ref("Couldn't load source status");
// `shallowRef`, not `ref`: the whole array is always replaced
// wholesale on load, never mutated in place, and `SourceOut.last_error`
// is the backend's recursive `JsonValue` type -- Vue's deep
// `UnwrapRef` mapped type recurses into it and TypeScript gives up
// with "Type instantiation is excessively deep" (TS2589).
const sources = shallowRef<SourceOut[]>([]);

const pollingAll = ref(false);
const pollingIds = ref<string[]>([]);

interface SnackbarState {
  text: string;
  color?: string;
}

const snackbar = ref<SnackbarState | null>(null);

function showSnackbar(text: string, color?: string): void {
  snackbar.value = { text, color };
}

/** Pre-resolved view data for one registration row. */
interface SourceRow {
  id: string;
  type: string;
  intake: string;
  publishedRef: string;
  enabled: boolean;
  pollable: boolean;
  statusLabel: StatusLabel;
  lastAttempt: { relative: string; absolute: string } | null;
  lastSuccess: { relative: string; absolute: string } | null;
  problem: SourceProblemDisplay;
  hint: string | null;
}

function describeError(error: unknown): string {
  if (isForbidden(error)) {
    return forbiddenText(error);
  }
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
    errorTitle.value = isForbidden(error) ? "No access" : "Couldn't load source status";
    errorText.value = describeError(error);
    loadState.value = "error";
  }
}

onMounted(load);

// A completed poll's effect on `last_attempt_at`/`last_status` lands
// a few seconds after the 202 response (it runs in a background
// task) -- refresh a few times with backoff instead of busy-looping,
// and cancel any pending refresh if the view unmounts first.
const REFRESH_DELAYS_MS = [1500, 4000, 9000];
let refreshTimers: ReturnType<typeof setTimeout>[] = [];

function scheduleStatusRefresh(): void {
  for (const delay of REFRESH_DELAYS_MS) {
    refreshTimers.push(setTimeout(() => void load(), delay));
  }
}

onUnmounted(() => {
  for (const timer of refreshTimers) {
    clearTimeout(timer);
  }
  refreshTimers = [];
});

function pollErrorText(error: unknown): string {
  if (isForbidden(error)) {
    return forbiddenText(error);
  }
  if (error instanceof ApiError) {
    if (error.status === 404) {
      return "That registration no longer exists in the configuration " +
        "loaded by the backend; reload this page.";
    }
    if (error.status === 409) {
      return errorDetail(error) ??
        "This registration cannot be polled right now (disabled or " +
          "push-only).";
    }
  }
  return "Could not start the poll. Check your connection and try again.";
}

async function pollAll(): Promise<void> {
  pollingAll.value = true;
  try {
    const result = await pollAllSources();
    showSnackbar(result.message, "success");
    scheduleStatusRefresh();
  } catch (error) {
    showSnackbar(pollErrorText(error), "error");
  } finally {
    pollingAll.value = false;
  }
}

async function pollOne(id: string): Promise<void> {
  pollingIds.value = [...pollingIds.value, id];
  try {
    const result = await pollSource(id);
    showSnackbar(result.message || `Poll started for ${id}.`, "success");
    scheduleStatusRefresh();
  } catch (error) {
    showSnackbar(pollErrorText(error), "error");
  } finally {
    pollingIds.value = pollingIds.value.filter((pending) => pending !== id);
  }
}

/** How to display a registration's problem, readably -- never the
 *  raw `last_error` JSON (audit finding S3). */
function problemDisplay(source: SourceOut): SourceProblemDisplay {
  if (source.config_error) {
    return { kind: "text", text: source.config_error };
  }
  return describeLastError(source.last_error);
}

/** A concrete next step for the operator, or `null` when healthy. */
function recoveryHint(source: SourceOut, problem: SourceProblemDisplay): string | null {
  const hasProblem = problem.kind !== "none";
  if (!hasProblem && source.last_status !== "failed" && source.last_status !== "partial") {
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
  const problem = problemDisplay(source);
  return {
    id: source.id,
    type: source.type,
    intake: source.intake.join(", "),
    publishedRef: source.published_ref,
    enabled: source.enabled,
    pollable: source.enabled && source.intake.includes("poll"),
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
    <div class="sources-header mb-4">
      <h1 id="sources-heading" class="text-h5">Sources</h1>
      <v-btn
        v-if="canOperate"
        color="primary"
        variant="tonal"
        prepend-icon="mdi-cloud-sync-outline"
        :loading="pollingAll"
        :disabled="pollingAll || loadState !== 'loaded'"
        @click="pollAll"
      >
        Poll all
      </v-btn>
    </div>

    <p v-if="!canOperate" class="text-body-2 text-medium-emphasis mb-4">
      Only operators can trigger polling. Ask an administrator for a role
      that grants the "operate" permission.
    </p>

    <LoadingState v-if="loadState === 'loading'" text="Loading source status…" />

    <ErrorState
      v-else-if="loadState === 'error'"
      :title="errorTitle"
      :text="errorText ?? undefined"
      @retry="load"
    />

    <template v-else>
      <div v-if="rows.length > 0" class="sources-table-scroll">
        <v-table>
          <thead>
            <tr>
              <th scope="col">Registration</th>
              <th scope="col">Type</th>
              <th scope="col">Intake</th>
              <th scope="col">Published ref</th>
              <th scope="col">Status</th>
              <th scope="col">Last attempt</th>
              <th scope="col">Last success</th>
              <th scope="col" class="problem-column">Problem &amp; recovery</th>
              <th v-if="canOperate" scope="col">Action</th>
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
              <td class="problem-column">
                <SourceProblemCell :problem="row.problem" :hint="row.hint" />
              </td>
              <td v-if="canOperate">
                <v-btn
                  v-if="row.pollable"
                  size="small"
                  variant="tonal"
                  prepend-icon="mdi-cloud-sync-outline"
                  :loading="pollingIds.includes(row.id)"
                  :disabled="pollingIds.includes(row.id)"
                  @click="pollOne(row.id)"
                >
                  Poll now
                </v-btn>
                <span v-else class="text-caption text-medium-emphasis">
                  Not pollable
                </span>
              </td>
            </tr>
          </tbody>
        </v-table>
      </div>

      <p v-else class="text-body-2 text-medium-emphasis">
        No source registrations are configured yet.
      </p>
    </template>

    <v-snackbar
      :model-value="snackbar !== null"
      :color="snackbar?.color"
      timeout="5000"
      @update:model-value="(value: boolean) => { if (!value) snackbar = null; }"
    >
      {{ snackbar?.text }}
      <template #actions>
        <v-btn variant="text" @click="snackbar = null">Dismiss</v-btn>
      </template>
    </v-snackbar>
  </section>
</template>

<style scoped>
.sources-header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

/* Scroll horizontally inside the table's own container, never the
 * page, so a wide table (long registration ids, many columns) never
 * causes page-level horizontal scroll and never clips the trailing
 * Action column (module-ux-principles accessibility; audit S3). */
.sources-table-scroll {
  overflow-x: auto;
}

/* Bound the problem/recovery column and let its text wrap instead of
 * growing the column (and the table) without limit. */
.problem-column {
  max-width: 22rem;
  white-space: normal;
  overflow-wrap: break-word;
}
</style>
