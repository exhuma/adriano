<script setup lang="ts">
/**
 * Record detail page's rendered-document card: the main column's
 * document body for an ordinary decision. One of the few places in
 * the app that use `v-html` (the other is `ErratumTextBlocks.vue`),
 * because `renderedHtml` is sanitized server-side at ingest time with
 * `nh3` before storage (see DECISIONS.md "Record schema"). An erratum
 * uses the dedicated `ErratumBody.vue` instead of this card. No
 * separate card title (R-03): the page's own `h1`, in `RecordHeader`,
 * already carries the title, and a leading markdown `h1` that repeats
 * it is skipped as well.
 */
import { computed } from "vue";

import { stripLeadingTitleHeading } from "@/utils/renderedHtml";

const props = defineProps<{
  /** Server-sanitized HTML of the document's rendered body. */
  renderedHtml: string;
  /** The record's own title, used only to detect and drop a leading
   *  markdown `h1` that duplicates the page's own `h1` (R-03). */
  title: string;
}>();

/** `renderedHtml` with a leading title-duplicate `h1` removed, when
 *  present. */
const bodyHtml = computed(() => stripLeadingTitleHeading(props.renderedHtml, props.title));
</script>

<template>
  <v-card class="mb-4">
    <v-card-text>
      <!-- eslint-disable-next-line vue/no-v-html -->
      <div class="rendered-markdown text-body-1" v-html="bodyHtml" />
    </v-card-text>
  </v-card>
</template>

<style scoped>
.rendered-markdown {
  /* No Vuetify utility wraps long unbroken tokens (URLs, identifiers)
     inside arbitrary markdown body HTML. */
  overflow-wrap: break-word;
  /* Vuetify has no ch-based measure utility (R-07: cap prose at
     ~70 characters per line); max-width is the only way to express
     it. */
  max-width: 70ch;
}
</style>
