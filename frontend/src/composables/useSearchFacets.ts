/**
 * Loads the catalog's search facets (sources and their projects) and
 * derives the `source`/`project` filter dropdown options from them,
 * narrowing the project list to the current source when one is
 * selected. Extracted from `SearchView.vue`
 * along a
 * natural seam: "load facets and keep the filter options/selection
 * consistent with them" is one cohesive responsibility, independent
 * of fetching search results for the committed query.
 */
import { computed, onMounted, ref, watch, type Ref } from "vue";

import { getFacets } from "@/api/records";
import type { FacetsOut } from "@/types/sources";

/** One labelled option for a `v-select`. */
export interface FacetOption<T> {
  title: string;
  value: T;
}

/**
 * :param source: The current `source` filter value.
 * :param project: The current `project` filter value; reset to `""`
 *     whenever it stops being a valid choice under `source`.
 * :returns: Whether loading the facets failed, and the derived
 *     source/project dropdown options.
 */
export function useSearchFacets(source: Ref<string>, project: Ref<string>) {
  const facets = ref<FacetsOut | null>(null);
  const facetsFailed = ref(false);

  onMounted(async () => {
    try {
      facets.value = await getFacets();
    } catch {
      facetsFailed.value = true;
    }
  });

  const sourceOptions = computed<FacetOption<string>[]>(() => {
    if (!facets.value) {
      return [];
    }
    return facets.value.sources.map((entry) => ({
      title: `${entry.source_id} (${entry.count})`,
      value: entry.source_id,
    }));
  });

  const projectOptions = computed<FacetOption<string>[]>(() => {
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

  // Changing the source narrows the project list; drop a project
  // that no longer belongs to it rather than silently keeping an
  // invisible filter active.
  watch(source, () => {
    if (project.value && !projectOptions.value.some((o) => o.value === project.value)) {
      project.value = "";
    }
  });

  return { facetsFailed, sourceOptions, projectOptions };
}
