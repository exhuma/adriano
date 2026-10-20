/**
 * Two-way URL sync for the search landing page's filters.
 *
 * Keeps `q`, `source`, `project`, `state`, `needs_approval`,
 * `record_type`, and `page` in the route's query string, so a search
 * is shareable by link and browser back/forward restores it
 * (module-ux-principles "Feedback & visibility of system status":
 * the URL is always an honest reflection of what is on screen).
 * Typing into the free-text field is debounced before it reaches the
 * URL -- and therefore before it triggers a new request -- while the
 * source/project/state/needs_approval/record_type filters and
 * pagination apply immediately. Changing any filter other than
 * `page` resets pagination back to page 1.
 */
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import type { LocationQueryRaw } from "vue-router";

import type {
  RecordState,
  RecordTypeFilter,
  SearchSort,
} from "@/types/records";

/** The state filter: one of the two record states, or "all". */
export type StateFilter = RecordState | "";

/** Decisions only (the default, omitted from the URL), to avoid
 *  cluttering shared links with the common case. */
export const DEFAULT_RECORD_TYPE: RecordTypeFilter = "decision";

const DEFAULT_DEBOUNCE_MS = 300;
const FILTER_KEYS = [
  "q",
  "source",
  "project",
  "state",
  "needs_approval",
  "record_type",
  "sort",
  "page",
] as const;

function readString(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function readBoolean(value: unknown): boolean {
  return value === "true";
}

function readPage(value: unknown): number {
  const parsed = Number.parseInt(readString(value), 10);
  return Number.isFinite(parsed) && parsed >= 1 ? parsed : 1;
}

/**
 * Normalise a raw `record_type` query value: an invalid or missing
 * value falls back to the default (decisions only), exactly like
 * {@link useSearchQuery} itself, so every reader of the URL agrees on
 * what counts as "the default" (SearchView's `committedParams` reads
 * this too, rather than re-validating the raw string itself).
 *
 * :param value: Raw `route.query.record_type` value.
 * :returns: A valid `RecordTypeFilter`, defaulting to `"decision"`.
 */
export function readRecordType(value: unknown): RecordTypeFilter {
  return value === "erratum" || value === "all" ? value : DEFAULT_RECORD_TYPE;
}

/** The sort used when `sort` is omitted: `relevance` when a query is
 *  set, else `title` (phases/11-ui-ux-updates.md decision 4;
 *  DECISIONS.md "HTTP API"). The backend applies the same default,
 *  so omitting `sort` from the URL/request when it equals this never
 *  changes what is actually requested. */
export function defaultSort(hasQuery: boolean): SearchSort {
  return hasQuery ? "relevance" : "title";
}

/**
 * Normalise a raw `sort` query value against whether a query is set.
 *
 * An unknown or missing value falls back to {@link defaultSort}, and
 * `"relevance"` without a query gracefully falls back to `"title"`
 * (DECISIONS.md: "relevance without q falls back to title") -- so a
 * stale or hand-edited URL (`sort=relevance` after `q` was removed)
 * never selects an option the sort `v-select` doesn't offer, exactly
 * like {@link readRecordType} does for `record_type`.
 *
 * :param value: Raw `route.query.sort` value.
 * :param hasQuery: Whether the free-text `q` filter is set.
 * :returns: A valid `SearchSort`.
 */
export function readSort(value: unknown, hasQuery: boolean): SearchSort {
  if (value === "relevance") {
    return hasQuery ? "relevance" : "title";
  }
  if (value === "title" || value === "recent") {
    return value;
  }
  return defaultSort(hasQuery);
}

/** Options for {@link useSearchQuery}. */
export interface UseSearchQueryOptions {
  /** Debounce delay (ms) applied to the free-text `q` filter. */
  debounceMs?: number;
}

/** Reactive filters kept in sync with the URL query string. */
export function useSearchQuery(options: UseSearchQueryOptions = {}) {
  const debounceMs = options.debounceMs ?? DEFAULT_DEBOUNCE_MS;
  const route = useRoute();
  const router = useRouter();

  const q = ref(readString(route.query.q));
  const source = ref(readString(route.query.source));
  const project = ref(readString(route.query.project));
  const state = ref<StateFilter>(readString(route.query.state) as StateFilter);
  const needsApproval = ref(readBoolean(route.query.needs_approval));
  const recordType = ref<RecordTypeFilter>(readRecordType(route.query.record_type));
  // The user's last explicit sort choice. Exposed as the writable
  // computed `sort` below, which re-applies `readSort`'s
  // relevance-needs-a-query rule on every read -- so clearing the
  // query flips the *effective* value (and the select's display)
  // straight to "title" through normal reactivity, with no separate
  // watcher needed to keep the two in sync.
  const rawSort = ref<SearchSort>(
    readSort(route.query.sort, Boolean(route.query.q)),
  );
  const sort = computed<SearchSort>({
    get: () => readSort(rawSort.value, q.value !== ""),
    set: (value) => {
      rawSort.value = value;
    },
  });
  const page = ref(readPage(route.query.page));

  let debounceTimer: ReturnType<typeof setTimeout> | undefined;

  function clearPendingDebounce(): void {
    if (debounceTimer !== undefined) {
      clearTimeout(debounceTimer);
      debounceTimer = undefined;
    }
  }

  function currentQuery(): LocationQueryRaw {
    return {
      q: q.value || undefined,
      source: source.value || undefined,
      project: project.value || undefined,
      state: state.value || undefined,
      needs_approval: needsApproval.value ? "true" : undefined,
      record_type: recordType.value !== DEFAULT_RECORD_TYPE ? recordType.value : undefined,
      sort: sort.value !== defaultSort(q.value !== "") ? sort.value : undefined,
      page: page.value > 1 ? String(page.value) : undefined,
    };
  }

  function matchesRoute(query: LocationQueryRaw): boolean {
    return FILTER_KEYS.every((key) => {
      const next = query[key] ?? undefined;
      const current = route.query[key] ?? undefined;
      return (next ?? "") === (current ?? "");
    });
  }

  function pushQuery(): void {
    const query = currentQuery();
    if (matchesRoute(query)) {
      return;
    }
    void router.replace({ query });
  }

  /** Resets pagination and applies a filter change, immediately or
   *  after the debounce delay. */
  function applyFilterChange(debounce: boolean): void {
    clearPendingDebounce();
    if (!debounce) {
      page.value = 1;
      pushQuery();
      return;
    }
    debounceTimer = setTimeout(() => {
      debounceTimer = undefined;
      page.value = 1;
      pushQuery();
    }, debounceMs);
  }

  watch(q, () => applyFilterChange(true));
  // `rawSort`, not the `sort` computed, is the watch source: an
  // explicit sort selection (which mutates `rawSort`) applies right
  // away, like the other immediate filters, but `sort`'s own
  // relevance-needs-a-query fallback firing because `q` changed must
  // not jump the URL ahead of `q`'s own debounce -- it is picked up
  // naturally once that debounce commits and `currentQuery()` reads
  // the (by-then up to date) `sort.value` getter.
  watch([source, project, state, needsApproval, recordType, rawSort], () =>
    applyFilterChange(false),
  );
  watch(page, () => pushQuery());

  // Restore filters on browser back/forward (or any external
  // navigation to this route with different query parameters). A
  // pending debounce from the field the user just left is discarded
  // so it cannot overwrite the state the user navigated to.
  watch(
    () => route.query,
    (query) => {
      clearPendingDebounce();
      const nextQ = readString(query.q);
      const nextSource = readString(query.source);
      const nextProject = readString(query.project);
      const nextState = readString(query.state) as StateFilter;
      const nextNeedsApproval = readBoolean(query.needs_approval);
      const nextRecordType = readRecordType(query.record_type);
      const nextSort = readSort(query.sort, Boolean(nextQ));
      const nextPage = readPage(query.page);
      if (q.value !== nextQ) q.value = nextQ;
      if (source.value !== nextSource) source.value = nextSource;
      if (project.value !== nextProject) project.value = nextProject;
      if (state.value !== nextState) state.value = nextState;
      if (needsApproval.value !== nextNeedsApproval) needsApproval.value = nextNeedsApproval;
      if (recordType.value !== nextRecordType) recordType.value = nextRecordType;
      if (sort.value !== nextSort) sort.value = nextSort;
      if (page.value !== nextPage) page.value = nextPage;
    },
  );

  onBeforeUnmount(clearPendingDebounce);

  /** Whether any filter (other than pagination) is currently set. */
  const hasActiveFilters = computed(
    () =>
      q.value !== "" ||
      source.value !== "" ||
      project.value !== "" ||
      state.value !== "" ||
      needsApproval.value ||
      recordType.value !== DEFAULT_RECORD_TYPE,
  );

  /** Resets every filter and pagination to defaults and clears the URL. */
  function clearFilters(): void {
    clearPendingDebounce();
    q.value = "";
    source.value = "";
    project.value = "";
    state.value = "";
    needsApproval.value = false;
    recordType.value = DEFAULT_RECORD_TYPE;
    sort.value = defaultSort(false);
    page.value = 1;
    void router.replace({ query: {} });
  }

  return {
    q,
    source,
    project,
    state,
    needsApproval,
    recordType,
    sort,
    page,
    hasActiveFilters,
    clearFilters,
  };
}
