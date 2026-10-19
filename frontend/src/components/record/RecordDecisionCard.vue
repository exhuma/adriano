<script setup lang="ts">
/**
 * Record detail page's rendered-decision card. This is the only
 * place in the app that uses `v-html`, because `renderedHtml` is
 * sanitized server-side at ingest time with `nh3` before storage
 * (see DECISIONS.md "Record schema").
 */
defineProps<{
  /** Server-sanitized HTML of the decision's rendered body. */
  renderedHtml: string;
}>();
</script>

<template>
  <v-card class="mb-4" variant="outlined">
    <v-card-title class="text-subtitle-1">Decision record</v-card-title>
    <v-card-text>
      <!-- eslint-disable-next-line vue/no-v-html -->
      <div class="rendered-markdown" v-html="renderedHtml" />
    </v-card-text>
  </v-card>
</template>

<style scoped>
.rendered-markdown {
  overflow-wrap: break-word;
}
</style>
