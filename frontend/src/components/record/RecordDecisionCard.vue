<script setup lang="ts">
/**
 * Record detail page's rendered-document card: the main column's
 * document body for an ordinary decision. One of the few places in
 * the app that use `v-html` (the other is `ErratumTextBlocks.vue`),
 * because `renderedHtml` is sanitized server-side at ingest time with
 * `nh3` before storage (see DECISIONS.md "Record schema"). An erratum
 * uses the dedicated `ErratumBody.vue` instead of this card.
 */
defineProps<{
  /** Server-sanitized HTML of the document's rendered body. */
  renderedHtml: string;
}>();
</script>

<template>
  <v-card class="mb-4" variant="outlined">
    <v-card-title tag="h2" class="text-subtitle-1">Decision record</v-card-title>
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
