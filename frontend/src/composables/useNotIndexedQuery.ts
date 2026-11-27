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
import { ref, watch } from "vue";
import { useRoute } from "vue-router";

import { readPage, readString, useUrlQuerySync } from "@/composables/urlQuery";

const KEYS = ["source", "project", "reason", "origin", "page"] as const;

/** The origin filter: one intake, or `""` for both. */
export type OriginFilter = "poll" | "push" | "";

function readOrigin(value: unknown): OriginFilter {
  return value === "poll" || value === "push" ? value : "";
}

/** Reactive filters kept in sync with the URL query string. */
export function useNotIndexedQuery() {
  const route = useRoute();

  const source = ref(readString(route.query.source));
  const project = ref(readString(route.query.project));
  const reason = ref(readString(route.query.reason));
  const origin = ref<OriginFilter>(readOrigin(route.query.origin));
  const page = ref(readPage(route.query.page));

  const { applyFilterChange, clearFilters: clearUrlFilters } = useUrlQuerySync({
    keys: KEYS,
    page,
    currentQuery: () => ({
      source: source.value || undefined,
      project: project.value || undefined,
      reason: reason.value || undefined,
      origin: origin.value || undefined,
      page: page.value > 1 ? String(page.value) : undefined,
    }),
    restore: (query) => {
      source.value = readString(query.source);
      project.value = readString(query.project);
      reason.value = readString(query.reason);
      origin.value = readOrigin(query.origin);
      page.value = readPage(query.page);
    },
  });

  watch(project, () => applyFilterChange(true));
  watch([source, reason, origin], () => applyFilterChange(false));

  /** Resets every filter and pagination, and clears the URL. */
  function clearFilters(): void {
    clearUrlFilters(() => {
      source.value = "";
      project.value = "";
      reason.value = "";
      origin.value = "";
      page.value = 1;
    });
  }

  return { source, project, reason, origin, page, clearFilters };
}

export { readOrigin };
