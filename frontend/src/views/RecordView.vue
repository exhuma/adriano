<script setup lang="ts">
/**
 * Record detail placeholder. No `/api/v1/records/{id}` endpoint
 * exists yet (see handoff notes), so this view makes no API calls
 * and honestly states the feature is not available yet.
 */
import EmptyState from "@/components/EmptyState.vue";

defineProps<{
  /** Record id from the route, e.g. `/records/:id`. */
  id: string;
}>();
</script>

<template>
  <section aria-labelledby="record-heading">
    <h1 id="record-heading" class="text-h5 mb-4">Record {{ id }}</h1>

    <EmptyState
      icon="mdi-file-document-outline"
      title="Record details not available yet"
      text="Record detail pages are not implemented yet. This view will
        show the rendered decision, metadata, approval state, and
        history once the backend provides them."
    />
  </section>
</template>
