<script setup lang="ts">
/**
 * Sources status placeholder. No `/api/v1/sources` endpoint exists
 * yet (see handoff notes), so this view makes no API calls and
 * honestly states the feature is not available yet.
 */
import EmptyState from "@/components/EmptyState.vue";
</script>

<template>
  <section aria-labelledby="sources-heading">
    <h1 id="sources-heading" class="text-h5 mb-4">Sources</h1>

    <EmptyState
      icon="mdi-source-branch"
      title="Source status not available yet"
      text="Per-registration polling status and freshness are not
        implemented yet. This view will list configured sources and
        let operators trigger a poll once the backend provides them."
    />
  </section>
</template>
