/**
 * Two-way URL sync for the not-indexed list's filters.
 *
 * Keeps `source`, `project`, `reason`, `origin` and `page` in the
 * route's query string, so a filtered list is shareable by link (the
 * Sources page links here with `?source=<id>`) and back/forward
 * restores it. The project is typed free text and is debounced
 * before it reaches the URL; the other filters and pagination apply
 * immediately. Changing a filter resets pagination to page 1.
 */
import { onBeforeUnmount, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import type { LocationQueryRaw } from "vue-router";

const DEBOUNCE_MS = 300;
const KEYS = ["source", "project", "reason", "origin", "page"] as const;

/** The origin filter: one intake, or `""` for both. */
export type OriginFilter = "poll" | "push" | "";

function readString(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function readOrigin(value: unknown): OriginFilter {
  return value === "poll" || value === "push" ? value : "";
}

function readPage(value: unknown): number {
  const parsed = Number.parseInt(readString(value), 10);
  return Number.isFinite(parsed) && parsed >= 1 ? parsed : 1;
}

/** Reactive filters kept in sync with the URL query string. */
export function useNotIndexedQuery() {
  const route = useRoute();
  const router = useRouter();

  const source = ref(readString(route.query.source));
  const project = ref(readString(route.query.project));
  const reason = ref(readString(route.query.reason));
  const origin = ref<OriginFilter>(readOrigin(route.query.origin));
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
      source: source.value || undefined,
      project: project.value || undefined,
      reason: reason.value || undefined,
      origin: origin.value || undefined,
      page: page.value > 1 ? String(page.value) : undefined,
    };
  }

  function pushQuery(): void {
    const query = currentQuery();
    const unchanged = KEYS.every(
      (key) => (query[key] ?? "") === (route.query[key] ?? ""),
    );
    if (!unchanged) {
      void router.replace({ query });
    }
  }

  function applyFilterChange(debounce: boolean): void {
    clearPendingDebounce();
    const apply = (): void => {
      debounceTimer = undefined;
      page.value = 1;
      pushQuery();
    };
    if (debounce) {
      debounceTimer = setTimeout(apply, DEBOUNCE_MS);
    } else {
      apply();
    }
  }

  watch(project, () => applyFilterChange(true));
  watch([source, reason, origin], () => applyFilterChange(false));
  watch(page, () => pushQuery());

  // Restore filters on back/forward; a pending debounce from the
  // field the user just left must not overwrite the restored state.
  watch(
    () => route.query,
    (query) => {
      clearPendingDebounce();
      source.value = readString(query.source);
      project.value = readString(query.project);
      reason.value = readString(query.reason);
      origin.value = readOrigin(query.origin);
      page.value = readPage(query.page);
    },
  );

  onBeforeUnmount(clearPendingDebounce);

  /** Resets every filter and pagination, and clears the URL. */
  function clearFilters(): void {
    clearPendingDebounce();
    source.value = "";
    project.value = "";
    reason.value = "";
    origin.value = "";
    page.value = 1;
    void router.replace({ query: {} });
  }

  return { source, project, reason, origin, page, clearFilters };
}

export { readOrigin, readPage, readString };
