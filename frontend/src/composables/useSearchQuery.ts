/**
 * Two-way URL sync for the search landing page's filters.
 *
 * Keeps `q`, `source`, `project`, `state`, and `page` in the route's
 * query string, so a search is shareable by link and browser
 * back/forward restores it (module-ux-principles "Feedback &
 * visibility of system status": the URL is always an honest
 * reflection of what is on screen). Typing into the free-text field
 * is debounced before it reaches the URL -- and therefore before it
 * triggers a new request -- while the source/project/state filters
 * and pagination apply immediately. Changing any filter other than
 * `page` resets pagination back to page 1.
 */
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import type { LocationQueryRaw } from "vue-router";

import type { RecordState } from "@/types/records";

/** The state filter: one of the two record states, or "all". */
export type StateFilter = RecordState | "";

const DEFAULT_DEBOUNCE_MS = 300;
const FILTER_KEYS = ["q", "source", "project", "state", "page"] as const;

function readString(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function readPage(value: unknown): number {
  const parsed = Number.parseInt(readString(value), 10);
  return Number.isFinite(parsed) && parsed >= 1 ? parsed : 1;
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
  watch([source, project, state], () => applyFilterChange(false));
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
      const nextPage = readPage(query.page);
      if (q.value !== nextQ) q.value = nextQ;
      if (source.value !== nextSource) source.value = nextSource;
      if (project.value !== nextProject) project.value = nextProject;
      if (state.value !== nextState) state.value = nextState;
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
      state.value !== "",
  );

  /** Resets every filter and pagination to defaults and clears the URL. */
  function clearFilters(): void {
    clearPendingDebounce();
    q.value = "";
    source.value = "";
    project.value = "";
    state.value = "";
    page.value = 1;
    void router.replace({ query: {} });
  }

  return { q, source, project, state, page, hasActiveFilters, clearFilters };
}
