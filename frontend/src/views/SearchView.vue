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
import EmptyState from "@/components/EmptyState.vue";
import ErrorState from "@/components/ErrorState.vue";
import LoadingState from "@/components/LoadingState.vue";
import StatusChip from "@/components/StatusChip.vue";
import { useSearchQuery } from "@/composables/useSearchQuery";
import { withLoading } from "@/composables/useLoading";
import type { RecordState, SearchItem, SearchPage, SearchParams } from "@/types/records";
import type { FacetsOut } from "@/types/sources";
import {
  approvalStateLabel,
  issueIndicatorLabel,
  recordStateLabel,
} from "@/utils/labels";

const PAGE_SIZE = 20;

const route = useRoute();
const { q, source, project, state, page, clearFilters } = useSearchQuery();

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
const results = ref<SearchPage | null>(null);

/** The committed (already-debounced) query, read from the URL
 *  itself so fetches never race ahead of the debounce delay. */
const committedParams = computed<SearchParams>(() => {
  const query = route.query;
  const rawState = typeof query.state === "string" ? query.state : undefined;
  const pageRaw = typeof query.page === "string" ? Number.parseInt(query.page, 10) : 1;
  return {
    q: typeof query.q === "string" ? query.q : undefined,
    source: typeof query.source === "string" ? query.source : undefined,
    project: typeof query.project === "string" ? query.project : undefined,
    state: (rawState as RecordState | undefined) ?? undefined,
    page: Number.isFinite(pageRaw) && pageRaw >= 1 ? pageRaw : 1,
    page_size: PAGE_SIZE,
  };
});

const hasActiveFilters = computed(
  () =>
    Boolean(committedParams.value.q) ||
    Boolean(committedParams.value.source) ||
    Boolean(committedParams.value.project) ||
    Boolean(committedParams.value.state),
);

function describeError(error: unknown): string {
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

      <v-btn
        variant="text"
        prepend-icon="mdi-filter-remove-outline"
        :disabled="!hasActiveFilters"
        @click="clearFilters"
      >
        Clear filters
      </v-btn>
    </div>

    <p class="sr-only" role="status" aria-live="polite">{{ resultSummary }}</p>

    <div v-if="loadState === 'loading'">
      <LoadingState text="Searching the catalog…" />
    </div>

    <ErrorState
      v-else-if="loadState === 'error'"
      title="Couldn't load search results"
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
            Clear filters
          </v-btn>
        </template>
      </EmptyState>

      <template v-else>
        <p class="text-body-2 text-medium-emphasis mt-4" aria-hidden="true">
          {{ resultSummary }}
        </p>

        <!--
          A plain flex layout, not `v-list-item`'s `#append` slot:
          that slot reserves a fixed-width column for the chips which
          squeezes (and mid-word-wraps) the title/subtitle text at
          narrow viewports.
        -->
        <ul class="results-list">
          <li v-for="item in results.items" :key="item.id" class="result-row">
            <router-link :to="recordHref(item)" class="result-link">
              <div class="result-text">
                <span class="text-subtitle-1">{{ item.title }}</span>
                <span class="text-body-2 text-medium-emphasis">
                  {{ item.source_id }} / {{ item.project }}
                </span>
              </div>
              <div class="result-chips">
                <StatusChip v-bind="recordStateLabel(item.kind, item.ref)" />
                <StatusChip
                  v-bind="approvalStateLabel(item.approval_state, item.kind)"
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

.results-list {
  list-style: none;
  margin: 0.5rem 0 0;
  padding: 0;
}

.result-row + .result-row {
  border-top: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}

.result-link {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem 1rem;
  padding: 0.75rem 0.25rem;
  color: inherit;
  text-decoration: none;
}

.result-link:hover,
.result-link:focus-visible {
  background: rgba(var(--v-theme-on-surface), 0.04);
}

.result-text {
  display: flex;
  flex-direction: column;
  min-width: 12rem;
  flex: 1 1 16rem;
}

.result-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.375rem;
  justify-content: flex-end;
  flex: 0 1 auto;
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
