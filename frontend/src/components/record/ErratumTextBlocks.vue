<script setup lang="ts">
/**
 * An erratum's "says" / "should say" text, shown both inline in
 * `ErrataSection.vue` (per erratum) and as the main content of
 * `ErratumBody.vue` (an erratum's own page). One of the few places in
 * the app that use `v-html` (the other is `RecordDecisionCard.vue`),
 * because every HTML field here is sanitized server-side at ingest
 * time with `nh3` before storage.
 * Each block is labelled and set off with a border, so the original
 * and corrected text are never distinguished by colour alone
 * (module-ux-principles "Do not rely on color alone"). The original
 * text is optional (e.g. a pure addition has nothing to quote). Set
 * at body-1 size with a ~70ch measure, consistent with the decision
 * record's own prose (R-07, `RecordDecisionCard.vue`).
 */
defineProps<{
  /** Server-sanitized HTML of the text the ADR currently says, or
   *  `null` when the erratum reports a pure addition. */
  originalHtml: string | null;
  /** Server-sanitized HTML of the text it should say. */
  correctedHtml: string;
  /** Server-sanitized HTML of the reporter's rationale, or `null`. */
  notesHtml: string | null;
}>();
</script>

<template>
  <!-- `text-break` here, not on each `.erratum-block-body` below, so
       every `eslint-disable-next-line` comment stays adjacent to its
       `v-html` line (`overflow-wrap`/`word-break` are inherited, so
       this still reaches all three quoted blocks). -->
  <div
    class="erratum-text-blocks d-flex flex-column ga-3 text-body-large
      text-break"
  >
    <div v-if="originalHtml" class="erratum-block">
      <p class="text-label-large mb-1">Original text — says:</p>
      <!-- eslint-disable-next-line vue/no-v-html -->
      <blockquote class="erratum-block-body ma-0 pl-3" v-html="originalHtml" />
    </div>

    <div class="erratum-block">
      <p class="text-label-large mb-1">Corrected text — should say:</p>
      <!-- eslint-disable-next-line vue/no-v-html -->
      <blockquote class="erratum-block-body ma-0 pl-3" v-html="correctedHtml" />
    </div>

    <div v-if="notesHtml" class="erratum-block">
      <p class="text-label-large mb-1">Notes</p>
      <!-- eslint-disable-next-line vue/no-v-html -->
      <div class="erratum-block-body ma-0 pl-3" v-html="notesHtml" />
    </div>
  </div>
</template>

<style scoped>
.erratum-text-blocks {
  /* Vuetify has no ch-based measure utility (R-07: cap prose at
     ~70 characters per line); max-width is the only way to express
     it. */
  max-width: 70ch;
}

.erratum-block-body {
  /* Vuetify's border utilities only toggle a themed 1px border; this
     accent rule needs an explicit 3px width, which has no utility
     equivalent. Long unbroken tokens (URLs, identifiers) inside the
     quoted HTML are wrapped by the `text-break` utility class at the
     call site instead of a custom rule. */
  border-left: 3px solid rgba(var(--v-border-color), var(--v-border-opacity));
}

/* Same last-resort heading rule as `RecordDecisionCard.vue`'s
   `.rendered-markdown` (see its comment for the full justification):
   this block's sanitized HTML can in principle carry markdown
   headings too, so they get the same MD3-token sizing instead of the
   browser default. */
.erratum-block-body :deep(h1),
.erratum-block-body :deep(h2) {
  font-size: 1.375rem; /* MD3 title-large */
  font-weight: 400;
  line-height: 1.2727272727;
  letter-spacing: normal;
  margin-top: 1em;
  margin-bottom: 0.5em;
}

.erratum-block-body :deep(h3) {
  font-size: 1rem; /* MD3 title-medium */
  font-weight: 500;
  line-height: 1.5;
  letter-spacing: 0.009375em;
  margin-top: 1em;
  margin-bottom: 0.5em;
}

.erratum-block-body :deep(h4),
.erratum-block-body :deep(h5),
.erratum-block-body :deep(h6) {
  font-size: 0.875rem; /* MD3 title-small */
  font-weight: 500;
  line-height: 1.4285714286;
  letter-spacing: 0.0071428571em;
  margin-top: 1em;
  margin-bottom: 0.5em;
}

.erratum-block-body :deep(p),
.erratum-block-body :deep(ul),
.erratum-block-body :deep(ol) {
  margin-top: 0;
  margin-bottom: 1em;
}

.erratum-block-body :deep(:first-child) {
  margin-top: 0;
}

/* same reasoning as `RecordDecisionCard.vue`'s
   `.rendered-markdown :deep(a)` -- a markdown link here has no
   class hook, so it rendered in the browser's own link colour
   instead of the theme. `primary` clears 4.5:1 on `surface` in both
   themes (`tests/plugins/vuetify.test.ts`); no `:visited` variant
   is needed, since an explicit `color` already outranks the
   user-agent stylesheet's `:visited` default. */
.erratum-block-body :deep(a) {
  color: rgb(var(--v-theme-primary));
}
</style>
