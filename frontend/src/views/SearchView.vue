<script setup lang="ts">
/**
 * Catalog search landing page.
 *
 * The free-text search field is the primary control. All filters
 * (`q`, `source`, `project`, `state`) and pagination live in the URL
 * query string via `useSearchQuery`, so a search is shareable by
 * link and restored by back/forward navigation. Results are fetched
 * only when the *committed* (debounced) URL query changes, never on
 * every keystroke.
 */
import { computed, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";

import { ApiError } from "@/api";
import { getFacets, searchRecords } from "@/api/records";
import { forbiddenText, isForbidden } from "@/utils/apiErrors";
import EmptyState from "@/components/EmptyState.vue";
import ErrorState from "@/components/ErrorState.vue";
import LoadingState from "@/components/LoadingState.vue";
import StatusChip from "@/components/StatusChip.vue";
import {
  DEFAULT_RECORD_TYPE,
  readRecordType,
  useSearchQuery,
} from "@/composables/useSearchQuery";
import { withLoading } from "@/composables/useLoading";
import type {
  RecordState,
  SearchItem,
  SearchPage,
  SearchParams,
} from "@/types/records";
import type { FacetsOut } from "@/types/sources";
import {
  candidateBranchText,
  issueIndicatorLabel,
  recordKindTypeLabel,
  searchApprovalStateLabel,
  searchErratumStatusLabel,
  searchRecordStateLabel,
} from "@/utils/labels";

const PAGE_SIZE = 20;

const route = useRoute();
const { q, source, project, state, needsApproval, recordType, page, clearFilters } =
  useSearchQuery();

const facets = ref<FacetsOut | null>(null);
const facetsFailed = ref(false);

onMounted(async () => {
  try {
    facets.value = await getFacets();
  } catch {
    facetsFailed.value = true;
  }
});

const sourceOptions = computed(() => {
  if (!facets.value) {
    return [];
  }
  return facets.value.sources.map((entry) => ({
    title: `${entry.source_id} (${entry.count})`,
    value: entry.source_id,
  }));
});

const projectOptions = computed(() => {
  if (!facets.value) {
    return [];
  }
  if (source.value) {
    const match = facets.value.sources.find(
      (entry) => entry.source_id === source.value,
    );
    return (match?.projects ?? []).map((entry) => ({
      title: `${entry.project} (${entry.count})`,
      value: entry.project,
    }));
  }
  const merged = new Map<string, number>();
  for (const entry of facets.value.sources) {
    for (const proj of entry.projects) {
      merged.set(proj.project, (merged.get(proj.project) ?? 0) + proj.count);
    }
  }
  return [...merged.entries()].map(([value, count]) => ({
    title: `${value} (${count})`,
    value,
  }));
});

// Changing the source narrows the project list; drop a project that
// no longer belongs to it rather than silently keeping an invisible
// filter active.
watch(source, () => {
  if (project.value && !projectOptions.value.some((o) => o.value === project.value)) {
    project.value = "";
  }
});

type LoadState = "loading" | "loaded" | "error";

const loadState = ref<LoadState>("loading");
const errorText = ref<string | null>(null);
const errorTitle = ref("Couldn't load search results");
const results = ref<SearchPage | null>(null);

/** The committed (already-debounced) query, read from the URL
 *  itself so fetches never race ahead of the debounce delay. */
const committedParams = computed<SearchParams>(() => {
  const query = route.query;
  const rawState = typeof query.state === "string" ? query.state : undefined;
  // Mirror `useSearchQuery`'s own normalisation: an invalid value
  // falls back to the default (decisions only), and the default is
  // never sent as an explicit filter, so a hand-edited or stale URL
  // behaves exactly like one with `record_type` omitted.
  const normalizedRecordType = readRecordType(query.record_type);
  const pageRaw = typeof query.page === "string" ? Number.parseInt(query.page, 10) : 1;
  return {
    q: typeof query.q === "string" ? query.q : undefined,
    source: typeof query.source === "string" ? query.source : undefined,
    project: typeof query.project === "string" ? query.project : undefined,
    state: (rawState as RecordState | undefined) ?? undefined,
    needs_approval: query.needs_approval === "true" ? true : undefined,
    record_type:
      normalizedRecordType === DEFAULT_RECORD_TYPE ? undefined : normalizedRecordType,
    page: Number.isFinite(pageRaw) && pageRaw >= 1 ? pageRaw : 1,
    page_size: PAGE_SIZE,
  };
});

const hasActiveFilters = computed(
  () =>
    Boolean(committedParams.value.q) ||
    Boolean(committedParams.value.source) ||
    Boolean(committedParams.value.project) ||
    Boolean(committedParams.value.state) ||
    Boolean(committedParams.value.needs_approval) ||
    Boolean(committedParams.value.record_type),
);

function describeError(error: unknown): string {
  if (isForbidden(error)) {
    return forbiddenText(error);
  }
  if (error instanceof ApiError) {
    return `The catalog could not be searched (status ${error.status}). ` +
      "Check your connection and try again.";
  }
  return "The catalog could not be searched. Check your connection and try again.";
}

async function fetchResults(): Promise<void> {
  loadState.value = "loading";
  errorText.value = null;
  try {
    const page_result = await withLoading(() => searchRecords(committedParams.value));
    results.value = page_result;
    loadState.value = "loaded";
  } catch (error) {
    errorTitle.value = isForbidden(error) ? "No access" : "Couldn't load search results";
    errorText.value = describeError(error);
    loadState.value = "error";
  }
}

watch(committedParams, fetchResults, { immediate: true });

const pageCount = computed(() =>
  results.value ? Math.max(1, Math.ceil(results.value.total / results.value.page_size)) : 1,
);

const resultSummary = computed(() => {
  if (loadState.value !== "loaded" || !results.value) {
    return "";
  }
  const { total } = results.value;
  if (total === 0) {
    return "No records found.";
  }
  const start = (results.value.page - 1) * results.value.page_size + 1;
  const end = Math.min(total, results.value.page * results.value.page_size);
  return `Showing ${start}–${end} of ${total} record${total === 1 ? "" : "s"}.`;
});

function recordHref(item: SearchItem): string {
  return `/records/${item.id}`;
}

/** The no-matches empty state's clear-action label: "Clear search
 *  and filters" once a query is set, since the action also clears
 *  the free-text query and the plain "filters" wording under-states
 *  that then (S-07); "Clear filters" otherwise. */
const clearActionLabel = computed(() =>
  committedParams.value.q ? "Clear search and filters" : "Clear filters",
);

/** The result row's primary title: for an erratum, "Erratum for
 *  <target>" leads (so two rows both stored as "Erratum: Decision"
 *  are distinguishable by their target), with the erratum's own
 *  stored title shown as a secondary line; an ordinary decision just
 *  shows its title. */
function rowTitle(item: SearchItem): string {
  if (item.record_kind !== "erratum") {
    return item.title;
  }
  return item.erratum_for_title
    ? `Erratum for ${item.erratum_for_title}`
    : "Erratum for an unknown decision";
}
</script>

<template>
  <section aria-labelledby="search-heading">
    <h1 id="search-heading" class="text-h5 mb-4">Search the ADR catalog</h1>

    <!--
      No `autofocus` here: it would steal initial keyboard focus from
      the "Skip to main content" link (module-ux-principles
      accessibility), which must stay first in tab order.
    -->
    <v-text-field
      v-model="q"
      label="Search decision records"
      placeholder="Search by title, UUID, project, or path"
      prepend-inner-icon="mdi-magnify"
      clearable
      variant="outlined"
      density="comfortable"
    />

    <div class="filters mt-2">
      <v-select
        v-model="source"
        :items="[{ title: 'All sources', value: '' }, ...sourceOptions]"
        label="Source"
        density="comfortable"
        variant="outlined"
        class="filter-select"
        :disabled="facetsFailed"
      />
      <v-select
        v-model="project"
        :items="[{ title: 'All projects', value: '' }, ...projectOptions]"
        label="Project"
        density="comfortable"
        variant="outlined"
        class="filter-select"
        :disabled="facetsFailed"
      />
      <v-btn-toggle
        v-model="state"
        mandatory
        density="comfortable"
        color="primary"
        variant="outlined"
        divided
        aria-label="Filter by publication state"
      >
        <v-btn value="" aria-label="Show all records">All</v-btn>
        <v-btn value="published" aria-label="Show published records only">
          Published
        </v-btn>
        <v-btn value="candidate" aria-label="Show candidate records only">
          Candidate
        </v-btn>
      </v-btn-toggle>

      <v-select
        v-model="recordType"
        :items="[
          { title: 'Decisions', value: 'decision' },
          { title: 'Errata', value: 'erratum' },
          { title: 'Both', value: 'all' },
        ]"
        label="Show"
        density="comfortable"
        variant="outlined"
        class="filter-select"
      />

      <v-switch
        v-model="needsApproval"
        label="Needs approval"
        hint="Pending, rejected, changed since acceptance, or no approval policy"
        persistent-hint
        density="comfortable"
        color="warning"
        class="needs-approval-switch"
      />

      <v-btn
        variant="text"
        prepend-icon="mdi-filter-remove-outline"
        :disabled="!hasActiveFilters"
        @click="clearFilters"
      >
        Clear filters
      </v-btn>
    </div>

    <p class="d-sr-only" role="status" aria-live="polite">
      {{ resultSummary }}
    </p>

    <div v-if="loadState === 'loading'">
      <LoadingState text="Searching the catalog…" />
    </div>

    <ErrorState
      v-else-if="loadState === 'error'"
      :title="errorTitle"
      :text="errorText ?? undefined"
      @retry="fetchResults"
    />

    <template v-else-if="results">
      <EmptyState
        v-if="results.total === 0 && !hasActiveFilters"
        class="mt-6"
        icon="mdi-file-document-outline"
        title="No indexed records yet"
        text="This catalog has not indexed any decision records yet. Once a
          source is configured and polled, records will appear here."
      />
      <EmptyState
        v-else-if="results.total === 0"
        class="mt-6"
        icon="mdi-filter-off-outline"
        title="No matches for your filters"
        text="Nothing in the catalog matches this search and filter
          combination."
      >
        <template #actions>
          <v-btn
            color="primary"
            variant="tonal"
            prepend-icon="mdi-filter-remove-outline"
            @click="clearFilters"
          >
            {{ clearActionLabel }}
          </v-btn>
        </template>
      </EmptyState>

      <template v-else>
        <p class="text-body-2 text-medium-emphasis mt-4" aria-hidden="true">
          {{ resultSummary }}
        </p>

        <!--
          Title on its own line; source/project, short status and
          issue chips share a left-aligned metadata line below it
          (phases/11-ui-ux-updates.md Task 3, S-01: chips sat
          1,100+ px from the title they describe). A plain flex
          layout, not `v-list-item`'s `#append` slot, which reserves
          a fixed-width column that squeezes (and mid-word-wraps) the
          title at narrow viewports.
        -->
        <ul class="results-list">
          <li v-for="item in results.items" :key="item.id" class="result-row">
            <router-link
              :to="recordHref(item)"
              class="result-link d-flex flex-column py-3 px-1
                text-decoration-none"
            >
              <span class="text-subtitle-1">{{ rowTitle(item) }}</span>
              <span
                v-if="item.record_kind === 'erratum'"
                class="text-body-2 text-medium-emphasis"
              >
                {{ item.title }}
              </span>
              <div class="d-flex flex-wrap align-center ga-2 mt-1">
                <span class="text-body-2 text-medium-emphasis">
                  {{ item.source_id }} / {{ item.project }}
                  <template v-if="candidateBranchText(item.kind, item.ref)">
                    · {{ candidateBranchText(item.kind, item.ref) }}
                  </template>
                </span>
                <StatusChip
                  v-if="searchRecordStateLabel(item.kind)"
                  v-bind="searchRecordStateLabel(item.kind)!"
                />
                <StatusChip
                  v-if="item.record_kind === 'erratum'"
                  v-bind="recordKindTypeLabel(item.record_kind)"
                />
                <StatusChip
                  v-if="item.record_kind === 'erratum'"
                  v-bind="searchErratumStatusLabel(item.approval_state)"
                />
                <StatusChip
                  v-else
                  v-bind="searchApprovalStateLabel(item.approval_state)"
                />
                <StatusChip
                  v-if="issueIndicatorLabel(item.issue_counts)"
                  v-bind="issueIndicatorLabel(item.issue_counts)!"
                />
              </div>
            </router-link>
          </li>
        </ul>

        <v-pagination
          v-if="pageCount > 1"
          v-model="page"
          :length="pageCount"
          class="mt-4"
          aria-label="Search results pages"
        />
      </template>
    </template>
  </section>
</template>

<style scoped>
.filters {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.75rem;
}

.filter-select {
  min-width: 10rem;
  max-width: 16rem;
  flex: 1 1 10rem;
}

.needs-approval-switch {
  flex: 0 0 auto;
  max-width: 18rem;
}

.results-list {
  /* No Vuetify utility removes a <ul>'s marker/indent or sets this
     one-off top margin. */
  list-style: none;
  margin: 0.5rem 0 0;
  padding: 0;
}

.result-row + .result-row {
  /* Divider between rows, in the theme's border token -- Vuetify has
     no prop for an adjacent-sibling border on a plain <li>. */
  border-top: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}

.result-link {
  /* No Vuetify utility sets an anchor's text colour to "inherit from
     context"; without this a router-link renders browser-default
     link blue. */
  color: inherit;
}

.result-link:hover,
.result-link:focus-visible {
  /* Hover/focus highlight at the theme's on-surface token, low
     opacity -- Vuetify has no built-in hover treatment for a plain
     router-link acting as a row. */
  background: rgba(var(--v-theme-on-surface), 0.04);
}
</style>
