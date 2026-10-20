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
  defaultSort,
  readRecordType,
  readSort,
  useSearchQuery,
} from "@/composables/useSearchQuery";
import { withLoading } from "@/composables/useLoading";
import type {
  RecordState,
  SearchItem,
  SearchPage,
  SearchParams,
  SearchSort,
} from "@/types/records";
import type { FacetsOut } from "@/types/sources";
import {
  activeFilterChips,
  type ActiveFilterChip,
  type FilterKey,
} from "@/utils/activeFilters";
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

/**
 * One shared control density for the whole filter bar
 * (phases/11-ui-ux-updates.md Task 4, S-03: "use one density for the
 * whole bar so every control shares a top line") -- a
 * `<v-defaults-provider>` (ladder step 3) rather than a global
 * default, since only this one region needs it.
 */
const filterBarDefaults = {
  VSelect: { density: "compact" },
  VBtnToggle: { density: "compact" },
  VBtn: { density: "compact" },
  VSwitch: { density: "compact" },
} as const;

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
  const rawQ = typeof query.q === "string" ? query.q : undefined;
  // Mirror `useSearchQuery`'s `sort` computed: `relevance` without a
  // query gracefully falls back to `title` (DECISIONS.md), so a
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
 * not narrows, the results, so it gets no chip
 * (phases/11-ui-ux-updates.md Task 4). `q` is excluded too -- see
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
 * The result-count line, now naming the active filters (S-04: "the
 * count line doesn't mention [the filter]"). When "Needs approval" is
 * the only active filter, the direct "N records need approval"
 * wording reads more naturally than a generic filter count; any
 * other combination (including needs-approval plus something else)
 * uses the generic "N filters active" form, since there is no single
 * sentence that reads naturally for every combination.
 */
const resultSummary = computed(() => {
  if (loadState.value !== "loaded" || !results.value) {
    return "";
  }
  const { total } = results.value;
  const chips = activeChips.value;
  if (total === 0) {
    return "No records found.";
  }
  const start = (results.value.page - 1) * results.value.page_size + 1;
  const end = Math.min(total, results.value.page * results.value.page_size);
  const plural = total === 1 ? "" : "s";
  if (chips.length === 1 && chips[0].key === "needsApproval") {
    return `${total} record${plural} need${total === 1 ? "s" : ""} approval.`;
  }
  const base = `Showing ${start}–${end} of ${total} record${plural}.`;
  if (chips.length === 0) {
    return base;
  }
  const filters = `${chips.length} filter${chips.length === 1 ? "" : "s"}`;
  return `${base} ${filters} active.`;
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

    <!--
      S-03: one `<v-defaults-provider>` density for every control in
      the bar, so they share a top line/height (ladder step 3);
      min/max-width via component props, not CSS, bound each select
      (ladder step 4).
    -->
    <v-defaults-provider :defaults="filterBarDefaults">
      <div class="d-flex flex-wrap align-center ga-3 mt-2">
        <v-select
          v-model="source"
          :items="[{ title: 'All sources', value: '' }, ...sourceOptions]"
          label="Source"
          variant="outlined"
          min-width="140"
          max-width="200"
          :disabled="facetsFailed"
        />
        <v-select
          v-model="project"
          :items="[{ title: 'All projects', value: '' }, ...projectOptions]"
          label="Project"
          variant="outlined"
          min-width="140"
          max-width="200"
          :disabled="facetsFailed"
        />
        <v-btn-toggle
          v-model="state"
          mandatory
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
          variant="outlined"
          min-width="130"
          max-width="170"
        />

        <v-select
          v-model="sort"
          :items="sortItems"
          label="Sort by"
          variant="outlined"
          min-width="200"
          max-width="220"
        />

        <!--
          S-03: the switch's two-line hint moved into a tooltip, with
          `hide-details` so removing it doesn't leave an empty
          message slot behind (G-09). The info button goes in
          `v-switch`'s own `#append` slot (forwarded straight to
          `VInput`'s prepend/control/append layout, per VSwitch's
          source) rather than a hand-rolled flex sibling, so it is
          always positioned after the control+label by Vuetify's own
          layout, not by assumptions about how wide the switch
          renders. `density="default"` overrides the bar's shared
          compact density for this one instance (ladder step 4: "set
          a prop at the call site only when that instance has to
          differ") -- `compact` density combined with `size="small"`
          put this icon button's hit target under the 24x24 px
          minimum (coordinator browser check). The button carries its
          own `aria-label` with the full hint text, so it stays
          accessible whether or not the hover/focus tooltip is open;
          `v-tooltip` with `activator="parent"` also wires a
          hover/focus-triggered tooltip onto that same (naturally
          focusable) button. Decision 2 / S-04: the switch's
          `color="primary"`, not `warning` -- a deliberate, reversible
          filter is not a warning.
        -->
        <v-switch
          v-model="needsApproval"
          label="Needs approval"
          color="primary"
          hide-details="auto"
        >
          <template #append>
            <!--
              `<v-icon>` is explicit, not left to `v-btn`'s `icon`
              prop to auto-render: once a `v-btn` with an `icon` prop
              also gets default-slot content (the `v-tooltip` below),
              Vuetify treats that as "custom content supplied" and
              silently stops auto-rendering the prop's icon, leaving
              an empty, invisible button (coordinator browser check:
              no glyph ever painted, at any size).
            -->
            <v-btn
              icon="mdi-information-outline"
              variant="text"
              density="default"
              :aria-label="`Needs approval means: ${needsApprovalHint}`"
            >
              <v-icon icon="mdi-information-outline" aria-hidden="true" />
              <v-tooltip activator="parent" location="top">
                {{ needsApprovalHint }}
              </v-tooltip>
            </v-btn>
          </template>
        </v-switch>
      </div>
    </v-defaults-provider>

    <!--
      S-04: the persistent active-filter row, between the bar and the
      results. Always mounted (never `v-if`-removed) so the
      `aria-live` region exists before its content changes, per the
      module-vue-vuetify mode-indicator rules; the chip row itself
      (not an extra hidden summary) is the content that changes.
      "Clear filters" moved here (coordinator browser check: it used
      to wrap onto its own line at 1920, no longer anchored "at the
      end" of anything) -- the mode-indicator rules call this out
      directly ("the indicator carries its own exit"), so an
      all-filters clear belongs beside the per-filter clears, not in
      the control bar above. Hidden (not just disabled) when nothing
      is active, matching the chips themselves having nothing to
      show.
    -->
    <div
      class="d-flex flex-wrap align-center ga-2"
      :class="{ 'mt-3': activeChips.length > 0 || hasActiveFilters }"
      role="status"
      aria-live="polite"
    >
      <v-chip
        v-for="chip in activeChips"
        :key="chip.key"
        :color="chip.color"
        :prepend-icon="chip.icon"
        closable
        :close-label="`Remove filter: ${chip.label}`"
        @click:close="clearFilter(chip.key)"
      >
        {{ chip.label }}
      </v-chip>

      <v-btn
        v-if="hasActiveFilters"
        variant="text"
        prepend-icon="mdi-filter-remove-outline"
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
/*
 * phases/11-ui-ux-updates.md Task 4 removed `.filters`, `.filter-select`,
 * and `.needs-approval-switch`: the filter bar's layout, density and
 * widths are now expressed through Vuetify itself -- `d-flex
 * flex-wrap align-center ga-3` utility classes on the bar, a
 * `<v-defaults-provider>` for its shared density, `min-width`/
 * `max-width` props on each select, and `<v-spacer>` to anchor
 * "Clear filters" -- with no custom CSS left for any of it.
 */

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
