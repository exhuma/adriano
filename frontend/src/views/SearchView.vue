<script setup lang="ts">
/**
 * Catalog search landing page.
 *
 * The search term is the primary control and is kept in sync with
 * the `q` URL query parameter so a search is shareable by link. No
 * backend search endpoint exists yet (see handoff notes), so results
 * are never fetched here; an honest empty state explains that the
 * catalog has no indexed records yet rather than showing fake data.
 */
import { ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import EmptyState from "@/components/EmptyState.vue";

const route = useRoute();
const router = useRouter();

const initialQuery =
  typeof route.query.q === "string" ? route.query.q : "";
const searchTerm = ref(initialQuery);

watch(searchTerm, (value) => {
  router.replace({
    query: { ...route.query, q: value || undefined },
  });
});

watch(
  () => route.query.q,
  (value) => {
    const next = typeof value === "string" ? value : "";
    if (next !== searchTerm.value) {
      searchTerm.value = next;
    }
  },
);
</script>

<template>
  <section aria-labelledby="search-heading">
    <h1 id="search-heading" class="text-h5 mb-4">Search the ADR catalog</h1>

    <v-text-field
      v-model="searchTerm"
      label="Search decision records"
      placeholder="Search by title, UUID, project, or path"
      prepend-inner-icon="mdi-magnify"
      clearable
      variant="outlined"
      density="comfortable"
      autofocus
    />

    <EmptyState
      class="mt-6"
      icon="mdi-file-document-outline"
      title="No indexed records yet"
      text="This catalog has not indexed any decision records yet. Once a
        source is configured and polled, records will appear here."
    />
  </section>
</template>
