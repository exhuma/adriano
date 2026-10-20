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
      <div class="rendered-markdown text-body-large" v-html="bodyHtml" />
    </v-card-text>
  </v-card>
</template>

<style scoped>
.rendered-markdown {
  /* No Vuetify utility wraps long unbroken tokens (URLs, identifiers)
     inside arbitrary markdown body HTML. */
  overflow-wrap: break-word;
  /* Vuetify has no ch-based measure utility (R-07: cap prose at
     ~70ch characters per line); max-width is the only way to express
     it. */
  max-width: 70ch;
}

/*
 * Server-rendered markdown headings (h1-h6, from `v-html`) have no
 * class hook, so Vuetify's component props/defaults (ladder steps
 * 1-4) cannot reach them, and `vite-plugin-vuetify`'s `settings.scss`
 * (step 5) only lets a SASS build-time map override the typography
 * *classes* -- it still cannot target a bare `<h2>` produced from
 * markdown at runtime. `vuetify/lib/styles/main.css` defines no
 * `--v-*-font-size` custom properties for its type scale either (only
 * `--v-font-body`/`--v-font-heading` for font family), so there is no
 * token to reference; this restates the MD3 tokens from that
 * stylesheet's `.text-title-large`/`-medium`/`-small` rules as a last
 * resort (ladder step 6). Sized so markdown content headings stay
 * below the page h1 (`text-headline-medium`, 28px) and the card
 * h2 section headings elsewhere on the page (`text-title-large`,
 * 22px) -- docs/ui-review G-05: h1/h2 land at the title-large size so
 * a markdown h2 like "Context" reads as a real section heading
 * without outweighing the page title; h3 at title-medium; h4-h6 at
 * title-small. Margins give the sections and paragraphs/lists a
 * deliberate vertical rhythm instead of the browser's own defaults.
 */
.rendered-markdown :deep(h1),
.rendered-markdown :deep(h2) {
  font-size: 1.375rem; /* MD3 title-large */
  font-weight: 400;
  line-height: 1.2727272727;
  letter-spacing: normal;
  margin-top: 1.5em;
  margin-bottom: 0.5em;
}

.rendered-markdown :deep(h3) {
  font-size: 1rem; /* MD3 title-medium */
  font-weight: 500;
  line-height: 1.5;
  letter-spacing: 0.009375em;
  margin-top: 1.25em;
  margin-bottom: 0.5em;
}

.rendered-markdown :deep(h4),
.rendered-markdown :deep(h5),
.rendered-markdown :deep(h6) {
  font-size: 0.875rem; /* MD3 title-small */
  font-weight: 500;
  line-height: 1.4285714286;
  letter-spacing: 0.0071428571em;
  margin-top: 1em;
  margin-bottom: 0.5em;
}

.rendered-markdown :deep(p),
.rendered-markdown :deep(ul),
.rendered-markdown :deep(ol) {
  margin-top: 0;
  margin-bottom: 1em;
}

.rendered-markdown :deep(:first-child) {
  margin-top: 0;
}
</style>
