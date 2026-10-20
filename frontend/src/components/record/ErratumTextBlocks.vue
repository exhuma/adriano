<script setup lang="ts">
/**
 * An erratum's "says" / "should say" text, shown both inline in
 * `ErrataSection.vue` (per erratum) and as the main content of
 * `ErratumBody.vue` (an erratum's own page). One of the few places in
 * the app that use `v-html` (the other is `RecordDecisionCard.vue`),
 * because every HTML field here is sanitized server-side at ingest
 * time with `nh3` before storage (see DECISIONS.md "Record schema").
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
  <div class="erratum-text-blocks d-flex flex-column ga-3 text-body-1">
    <div v-if="originalHtml" class="erratum-block">
      <p class="text-overline mb-1">Original text — says:</p>
      <!-- eslint-disable-next-line vue/no-v-html -->
      <blockquote class="erratum-block-body ma-0 pl-3" v-html="originalHtml" />
    </div>

    <div class="erratum-block">
      <p class="text-overline mb-1">Corrected text — should say:</p>
      <!-- eslint-disable-next-line vue/no-v-html -->
      <blockquote class="erratum-block-body ma-0 pl-3" v-html="correctedHtml" />
    </div>

    <div v-if="notesHtml" class="erratum-block">
      <p class="text-overline mb-1">Notes</p>
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
     equivalent. */
  border-left: 3px solid rgba(var(--v-border-color), var(--v-border-opacity));
  /* No Vuetify utility wraps long unbroken tokens (URLs,
     identifiers) inside quoted HTML at arbitrary widths. */
  overflow-wrap: break-word;
}
</style>
