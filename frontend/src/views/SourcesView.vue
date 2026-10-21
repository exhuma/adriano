<script setup lang="ts">
/**
 * Source registration status page: per-registration configuration,
 * freshness, and recovery hints, plus operator-triggered polling.
 *
 * "Poll all" and per-row "Poll now" are shown only to callers with
 * the `operate` permission (`useAuth().can("operate")`); everyone
 * else sees a short note, below the table, naming who can poll
 * instead of a disabled, unexplained control (module-ux-principles
 * "Write recovery messages for humans"). The same permission gates
 * the problem/recovery sub-row's content (env-var names, recovery
 * steps -- `SourceProblemCell`'s `canOperate` prop): a reader sees
 * status and dates only (phases/11-ui-ux-updates.md decision 3).
 */
import { computed, onMounted, onUnmounted, ref, shallowRef } from "vue";
import { useDisplay } from "vuetify";

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
import {
  pollStatusLabel,
  recoveryHint,
  staleStatusText,
  type StatusLabel,
} from "@/utils/labels";
import { describeLastError, type SourceProblemDisplay } from "@/utils/sourceErrors";

type LoadState = "loading" | "loaded" | "error";

const { can } = useAuth();
const canOperate = computed(() => can("operate"));

// Vuetify display breakpoints (step 4 of the "Vuetify first" ladder),
// not a custom media query: at `smAndDown` (<960px -- the 200%-zoom
// review viewport of 683 CSS px falls in `sm`) the Type/Intake/
// Published-ref columns fold into the Registration cell as secondary
// text instead of their own columns, so the row's remaining columns
// (Registration, Status, Last attempt, Last success, and an
// operator's Action) fit without the table ever needing to scroll
// horizontally to reach "Poll now" (P11-R-11).
const { smAndDown } = useDisplay();

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
  /** Secondary staleness note shown next to the status chip, or
   *  `null` -- never a second chip (docs/ui-review O-01). */
  staleText: string | null;
  lastAttempt: { relative: string; absolute: string } | null;
  lastSuccess: { relative: string; absolute: string } | null;
  problem: SourceProblemDisplay;
  hint: string | null;
  /** Whether this row has operator-relevant problem/recovery detail
   *  to show as a full-width sub-row (docs/ui-review O-03). */
  hasProblemDetail: boolean;
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
    return {
      kind: "config",
      code: source.config_error_code,
      text: source.config_error,
    };
  }
  return describeLastError(source.last_error);
}

/** A concrete next step for the operator, or `null` when healthy.
 *  Tailored per problem code (`recoveryHint` in `utils/labels/sources
 *  .ts`), not a single per-source-type sentence: that generic text
 *  used to recommend checking a token env var even for e.g.
 *  `removed_from_config`, which has no catalog.yaml entry left to
 *  check at all (Batch B follow-up to Task 8/R-10). */
function nextStep(
  source: SourceOut,
  problem: SourceProblemDisplay,
): string | null {
  const hasProblem = problem.kind !== "none";
  if (!hasProblem && source.last_status !== "failed" && source.last_status !== "partial") {
    return null;
  }
  return recoveryHint(problem, source.type);
}

/** Resolve the display-ready fields for one registration row once,
 *  so the template never re-derives them (and never has to narrow
 *  the recursive `JsonValue` type of `last_error` itself). */
function toRow(source: SourceOut): SourceRow {
  const problem = problemDisplay(source);
  const hint = nextStep(source, problem);
  return {
    id: source.id,
    type: source.type,
    intake: source.intake.join(", "),
    publishedRef: source.published_ref,
    enabled: source.enabled,
    pollable: source.enabled && source.intake.includes("poll"),
    statusLabel: pollStatusLabel(source.last_status, source.stale),
    staleText: staleStatusText(source.last_status, source.stale),
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
    hint,
    hasProblemDetail: problem.kind !== "none" || hint !== null,
  };
}

const rows = computed<SourceRow[]>(() => sources.value.map(toRow));

// Registration, Status, Last attempt, Last success are always their
// own columns; Type/Intake/Published ref fold into Registration below
// `sm` (P11-R-11); Action is an operator's own column. Used as the
// problem sub-row's `colspan` so it always spans every visible column
// (docs/ui-review O-03).
const columnCount = computed(
  () => 4 + (smAndDown.value ? 0 : 3) + (canOperate.value ? 1 : 0),
);
</script>

<template>
  <section aria-labelledby="sources-heading">
    <div class="d-flex flex-wrap align-center justify-space-between ga-3 mb-4">
      <h1 id="sources-heading" class="text-headline-medium font-weight-medium">
        Sources
      </h1>
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

    <LoadingState v-if="loadState === 'loading'" text="Loading source status…" />

    <ErrorState
      v-else-if="loadState === 'error'"
      :title="errorTitle"
      :text="errorText ?? undefined"
      @retry="load"
    />

    <template v-else>
      <div v-if="rows.length > 0">
        <v-table>
          <thead>
            <tr>
              <th scope="col" class="text-label-large text-medium-emphasis">
                Registration
              </th>
              <th
                v-if="!smAndDown"
                scope="col"
                class="text-label-large text-medium-emphasis"
              >
                Type
              </th>
              <th
                v-if="!smAndDown"
                scope="col"
                class="text-label-large text-medium-emphasis"
              >
                Intake
              </th>
              <th
                v-if="!smAndDown"
                scope="col"
                class="text-label-large text-medium-emphasis"
              >
                Published ref
              </th>
              <th scope="col" class="text-label-large text-medium-emphasis">
                Status
              </th>
              <th scope="col" class="text-label-large text-medium-emphasis">
                Last attempt
              </th>
              <th scope="col" class="text-label-large text-medium-emphasis">
                Last success
              </th>
              <th
                v-if="canOperate"
                scope="col"
                class="text-label-large text-medium-emphasis"
              >
                Action
              </th>
            </tr>
          </thead>
          <tbody>
            <template v-for="row in rows" :key="row.id">
              <tr>
                <th scope="row">
                  {{ row.id }}
                  <div
                    v-if="smAndDown"
                    class="text-body-small text-medium-emphasis"
                  >
                    {{
                      [row.type, row.intake, row.publishedRef]
                        .filter((part) => part)
                        .join(" · ")
                    }}
                  </div>
                </th>
                <td v-if="!smAndDown">{{ row.type }}</td>
                <td v-if="!smAndDown">{{ row.intake }}</td>
                <td v-if="!smAndDown">{{ row.publishedRef }}</td>
                <td>
                  <StatusChip v-bind="row.statusLabel" />
                  <div
                    v-if="row.staleText"
                    class="text-body-small text-medium-emphasis mt-1"
                  >
                    {{ row.staleText }}
                  </div>
                </td>
                <td>
                  <!--
                    docs/ui-review "New issues" #3 (Task 14
                    re-verification, Phase 11 Task 16 follow-up):
                    `d-inline-block py-1` so this focusable tooltip
                    trigger's own box is >=24px tall (it measured
                    82x16, as tall as its text line only).
                  -->
                  <span
                    v-if="row.lastAttempt"
                    tabindex="0"
                    class="date-tooltip-activator d-inline-block py-1"
                  >
                    {{ row.lastAttempt.relative }}
                    <span class="d-sr-only">
                      ({{ row.lastAttempt.absolute }})
                    </span>
                    <v-tooltip
                      activator="parent"
                      location="bottom"
                      :text="row.lastAttempt.absolute"
                    />
                  </span>
                  <span v-else>Never</span>
                </td>
                <td>
                  <span
                    v-if="row.lastSuccess"
                    tabindex="0"
                    class="date-tooltip-activator d-inline-block py-1"
                  >
                    {{ row.lastSuccess.relative }}
                    <span class="d-sr-only">
                      ({{ row.lastSuccess.absolute }})
                    </span>
                    <v-tooltip
                      activator="parent"
                      location="bottom"
                      :text="row.lastSuccess.absolute"
                    />
                  </span>
                  <span v-else>Never</span>
                </td>
                <td v-if="canOperate">
                  <v-btn
                    v-if="row.pollable"
                    color="primary"
                    variant="tonal"
                    prepend-icon="mdi-cloud-sync-outline"
                    :loading="pollingIds.includes(row.id)"
                    :disabled="pollingIds.includes(row.id)"
                    @click="pollOne(row.id)"
                  >
                    Poll now
                  </v-btn>
                  <span v-else class="text-body-small text-medium-emphasis">
                    Not pollable
                  </span>
                </td>
              </tr>
              <!-- Problem & recovery as a full-width sub-row, not a
                   ninth column (docs/ui-review O-03): at 200% zoom the
                   table no longer has to grow a dedicated, far-right
                   column to show it -- the detail a failing source's
                   operator needs most sits directly under that row
                   instead, and healthy rows (the common case) add no
                   row at all. -->
              <tr v-if="canOperate && row.hasProblemDetail">
                <td :colspan="columnCount" class="pt-0 pb-4">
                  <SourceProblemCell
                    :problem="row.problem"
                    :hint="row.hint"
                    :can-operate="canOperate"
                  />
                </td>
              </tr>
            </template>
          </tbody>
        </v-table>
      </div>

      <p v-else class="text-body-medium text-medium-emphasis">
        No source registrations are configured yet.
      </p>
    </template>

    <p
      v-if="!canOperate"
      class="text-body-small text-medium-emphasis mt-4 d-flex align-center ga-1"
    >
      <v-icon icon="mdi-information-outline" size="16" aria-hidden="true" />
      Only operators can trigger polling. Ask an administrator for a role
      that grants the "operate" permission.
    </p>

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

<!-- No local <style> block: `v-table`'s own `.v-table__wrapper` already
     scrolls horizontally (`overflow: auto` in Vuetify's VTable.css), so
     the formerly-added `.sources-table-scroll` wrapper only duplicated
     that scroll container without changing behaviour (P11-R-10). The
     `smAndDown` column fold above keeps every column, including the
     operator's Action button, reachable without any horizontal scroll
     at the 200%-zoom width that prompted it (P11-R-11); the table's
     built-in scroll remains the fallback for any still-wider content. -->
