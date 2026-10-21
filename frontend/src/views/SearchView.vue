<script setup lang="ts">
/**
 * Catalog search landing page.
 *
 * The free-text search field is the primary control. All filters
 * (`q`, `source`, `project`, `state`, `needs_approval`, `record_type`),
 * the sort order (`sort`; not itself a filter), and pagination live
 * in the URL query string via `useSearchQuery`, so a search is
 * shareable by link and restored by back/forward navigation. Results
 * are fetched only when the *committed* (debounced) URL query
 * changes, never on every keystroke.
 *
 * The filter bar, the active-filter chip row, and one result row are
 * each their own component (`SearchFilterBar`, `ActiveFilterRow`,
 * `SearchResultRow`),
 * so this view owns the page's data flow -- the committed query, the
 * fetch, and the active-filter chips -- while each extracted
 * component owns only how its own slice renders.
 */
import { computed, ref, watch } from "vue";
import { useRoute } from "vue-router";

import { ApiError } from "@/api";
import { searchRecords } from "@/api/records";
import { forbiddenText, isForbidden } from "@/utils/apiErrors";
import ActiveFilterRow from "@/components/search/ActiveFilterRow.vue";
import SearchFilterBar from "@/components/search/SearchFilterBar.vue";
import SearchResultRow from "@/components/search/SearchResultRow.vue";
import EmptyState from "@/components/EmptyState.vue";
import ErrorState from "@/components/ErrorState.vue";
import LoadingState from "@/components/LoadingState.vue";
import {
  DEFAULT_RECORD_TYPE,
  defaultSort,
  readRecordType,
  readSort,
  useSearchQuery,
} from "@/composables/useSearchQuery";
import { useSearchFacets } from "@/composables/useSearchFacets";
import { withLoading } from "@/composables/useLoading";
import type {
  RecordState,
  SearchPage,
  SearchParams,
  SearchSort,
} from "@/types/records";
import {
  activeFilterChips,
  type ActiveFilterChip,
  type FilterKey,
} from "@/utils/activeFilters";

const PAGE_SIZE = 20;

const route = useRoute();
const {
  q,
  source,
  project,
  state,
  needsApproval,
  recordType,
  sort,
  page,
  clearFilters,
} = useSearchQuery();

/** The needs-approval filter's full "what counts" explanation, used
 *  both as the info button's `aria-label` and the tooltip's text --
 *  a plain string constant, not an inline template attribute, so
 *  wrapping it across source lines never leaks a literal newline or
 *  indentation into the rendered (and announced) text. */
const needsApprovalHint =
  "pending, rejected, changed since acceptance, or no approval " +
  "policy configured";

/** The "Sort by" select's options: "Relevance" is only offered once a
 *  query is set (S-08; it ranks by text match, which is meaningless
 *  on an empty query). */
const sortItems = computed<{ title: string; value: SearchSort }[]>(() => {
  const items: { title: string; value: SearchSort }[] = [];
  if (q.value) {
    items.push({ title: "Relevance", value: "relevance" });
  }
  items.push({ title: "Title A–Z", value: "title" });
  items.push({ title: "Recently changed", value: "recent" });
  return items;
});

const { facetsFailed, sourceOptions, projectOptions } = useSearchFacets(
  source,
  project,
);

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
  const rawQ = typeof query.q === "string" ? query.q : undefined;
  // Mirror `useSearchQuery`'s `sort` computed: `relevance` without a
  // query gracefully falls back to `title`, so a
  // stale or hand-edited URL never sends a meaningless sort.
  const normalizedSort = readSort(query.sort, Boolean(rawQ));
  const pageRaw = typeof query.page === "string" ? Number.parseInt(query.page, 10) : 1;
  return {
    q: rawQ,
    source: typeof query.source === "string" ? query.source : undefined,
    project: typeof query.project === "string" ? query.project : undefined,
    state: (rawState as RecordState | undefined) ?? undefined,
    needs_approval: query.needs_approval === "true" ? true : undefined,
    record_type:
      normalizedRecordType === DEFAULT_RECORD_TYPE ? undefined : normalizedRecordType,
    sort:
      normalizedSort === defaultSort(Boolean(rawQ))
        ? undefined
        : normalizedSort,
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

/**
 * The active-filter mode chips (S-04), computed from the live filter
 * refs -- every filter but `q` already applies immediately (no
 * debounce), so the live refs and the committed/URL state agree by
 * the time a user can see a chip. `sort` is excluded: it reorders,
 * not narrows, the results, so it gets no chip. `q` is excluded too -- see
 * `activeFilterChips`'s own doc comment for why the search field
 * itself is that mode's continuous indicator.
 */
const activeChips = computed<ActiveFilterChip[]>(() =>
  activeFilterChips({
    needsApproval: needsApproval.value,
    source: source.value,
    project: project.value,
    state: state.value,
    recordType: recordType.value,
  }),
);

/** Clears exactly the one filter the closed chip named. */
function clearFilter(key: FilterKey): void {
  switch (key) {
    case "needsApproval":
      needsApproval.value = false;
      break;
    case "source":
      source.value = "";
      break;
    case "project":
      project.value = "";
      break;
    case "state":
      state.value = "";
      break;
    case "recordType":
      recordType.value = DEFAULT_RECORD_TYPE;
      break;
  }
}

/** Clears every active filter mode (every chip `ActiveFilterRow`
 *  shows), but leaves the free-text query and the sort order alone
 *  (P11-R-05): "Clear filters", beside the chips, should only undo
 *  what those chips represent -- unlike the empty-state "Clear
 *  search and filters" action below, which deliberately also clears
 *  `q`. */
function clearActiveFilters(): void {
  needsApproval.value = false;
  source.value = "";
  project.value = "";
  state.value = "";
  recordType.value = DEFAULT_RECORD_TYPE;
}

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

/**
 * The result-count line, naming the active filters (S-04: "the count
 * line doesn't mention [the filter]") while always keeping the page
 * range (P11-R-21: paging context must not vanish, even when "Needs
 * approval" is the only active filter). When it is the only active
 * filter, the range reads directly into "... that need approval."
 * instead of the generic "N filters active." suffix, since there is
 * no single generic sentence that reads naturally for every
 * combination (including needs-approval plus something else, which
 * still uses the generic form).
 */
const resultSummary = computed(() => {
  if (loadState.value !== "loaded" || !results.value) {
    return "";
  }
  const { total } = results.value;
  if (total === 0) {
    return "No records found.";
  }
  const chips = activeChips.value;
  const start = (results.value.page - 1) * results.value.page_size + 1;
  const end = Math.min(total, results.value.page * results.value.page_size);
  const plural = total === 1 ? "" : "s";
  const base = `Showing ${start}–${end} of ${total} record${plural}`;
  if (chips.length === 1 && chips[0].key === "needsApproval") {
    return `${base} that ${total === 1 ? "needs" : "need"} approval.`;
  }
  if (chips.length === 0) {
    return `${base}.`;
  }
  const filters = `${chips.length} filter${chips.length === 1 ? "" : "s"}`;
  return `${base}. ${filters} active.`;
});

/** The no-matches empty state's clear-action label: "Clear search
 *  and filters" once a query is set, since the action also clears
 *  the free-text query and the plain "filters" wording under-states
 *  that then (S-07); "Clear filters" otherwise. */
const clearActionLabel = computed(() =>
  committedParams.value.q ? "Clear search and filters" : "Clear filters",
);
</script>

<template>
  <section aria-labelledby="search-heading">
    <h1
      id="search-heading"
      class="text-headline-medium font-weight-medium mb-4"
    >
      Search the ADR catalog
    </h1>

    <!--
      No `autofocus` here: it would steal initial keyboard focus from
      the "Skip to main content" link (module-ux-principles
      accessibility), which must stay first in tab order.
    -->
    <!--
      S-06: capped via the `max-width` prop (ladder step 4) rather
      than sharing a row with the filters -- the free-text query
      stays the page's one primary control, per the module docstring
      above.
    -->
    <v-text-field
      v-model="q"
      label="Search decision records"
      placeholder="Search by title, UUID, project, or path"
      prepend-inner-icon="mdi-magnify"
      clearable
      variant="outlined"
      density="comfortable"
      max-width="720"
    />

    <SearchFilterBar
      v-model:source="source"
      v-model:project="project"
      v-model:state="state"
      v-model:record-type="recordType"
      v-model:sort="sort"
      v-model:needs-approval="needsApproval"
      :source-options="sourceOptions"
      :project-options="projectOptions"
      :sort-items="sortItems"
      :facets-failed="facetsFailed"
      :needs-approval-hint="needsApprovalHint"
    />

    <!--
      S-04: the persistent active-filter row, between the bar and
      the results -- always mounted (never `v-if`-removed), per the
      module-vue-vuetify mode-indicator rules. See
      `components/search/ActiveFilterRow.vue` for the live-region and
      "Clear filters" scope/placement rules (P11-R-05).
    -->
    <ActiveFilterRow
      :chips="activeChips"
      @clear-filter="clearFilter"
      @clear-filters="clearActiveFilters"
    />

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
        <p
          class="text-body-medium text-medium-emphasis mt-4"
          aria-hidden="true"
        >
          {{ resultSummary }}
        </p>

        <ul class="results-list ma-0 mt-2 pa-0">
          <SearchResultRow
            v-for="(item, index) in results.items"
            :key="item.id"
            :item="item"
            :divided="index > 0"
          />
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
.results-list {
  /* No Vuetify utility removes a <ul>'s marker/indent; margin and
     padding are zeroed/set through utility classes on the element
     instead (`ma-0 mt-2 pa-0`, ladder step 4). */
  list-style: none;
}
</style>
