/**
 * Shared plumbing for the composables that keep list filters in the
 * route's query string (`useSearchQuery`, `useNotIndexedQuery`): the
 * query-value readers and a debounced, two-way URL sync.
 */
import { onBeforeUnmount, watch } from "vue";
import type { Ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import type { LocationQuery, LocationQueryRaw } from "vue-router";

/** Default debounce (ms) for typed free-text filters. */
export const DEFAULT_DEBOUNCE_MS = 300;

/** A query value as a string; anything else reads as `""`. */
export function readString(value: unknown): string {
  return typeof value === "string" ? value : "";
}

/** A 1-based page number; anything invalid reads as page 1. */
export function readPage(value: unknown): number {
  const parsed = Number.parseInt(readString(value), 10);
  return Number.isFinite(parsed) && parsed >= 1 ? parsed : 1;
}

/** Options for {@link useUrlQuerySync}. */
export interface UrlQuerySyncOptions {
  /** Every query key the composable owns (compared before a push). */
  keys: readonly string[];
  /** The query the current filter state maps to. */
  currentQuery: () => LocationQueryRaw;
  /** The pagination ref; reset to 1 when a filter changes. */
  page: Ref<number>;
  /** Writes a navigated-to route query back into the filter refs. */
  restore: (query: LocationQuery) => void;
  /** Debounce delay (ms) for debounced filter changes. */
  debounceMs?: number;
}

/**
 * Debounced two-way sync between filter refs and the URL query.
 *
 * The caller watches its own filter refs and calls
 * `applyFilterChange`; pagination changes and external navigation
 * (back/forward) are handled here.
 */
export function useUrlQuerySync(options: UrlQuerySyncOptions) {
  const { keys, currentQuery, page, restore } = options;
  const debounceMs = options.debounceMs ?? DEFAULT_DEBOUNCE_MS;
  const route = useRoute();
  const router = useRouter();

  let debounceTimer: ReturnType<typeof setTimeout> | undefined;

  function clearPendingDebounce(): void {
    if (debounceTimer !== undefined) {
      clearTimeout(debounceTimer);
      debounceTimer = undefined;
    }
  }

  function pushQuery(): void {
    const query = currentQuery();
    const unchanged = keys.every(
      (key) => (query[key] ?? "") === (route.query[key] ?? ""),
    );
    if (!unchanged) {
      void router.replace({ query });
    }
  }

  /** Resets pagination and applies a filter change, immediately or
   *  after the debounce delay. */
  function applyFilterChange(debounce: boolean): void {
    clearPendingDebounce();
    const apply = (): void => {
      debounceTimer = undefined;
      page.value = 1;
      pushQuery();
    };
    if (debounce) {
      debounceTimer = setTimeout(apply, debounceMs);
    } else {
      apply();
    }
  }

  watch(page, () => pushQuery());

  // Restore filters on back/forward; a pending debounce from the
  // field the user just left must not overwrite the restored state.
  watch(
    () => route.query,
    (query) => {
      clearPendingDebounce();
      restore(query);
    },
  );

  onBeforeUnmount(clearPendingDebounce);

  /** Runs `reset` (which empties the filter refs) and clears the URL. */
  function clearFilters(reset: () => void): void {
    clearPendingDebounce();
    reset();
    void router.replace({ query: {} });
  }

  return { applyFilterChange, clearFilters };
}
