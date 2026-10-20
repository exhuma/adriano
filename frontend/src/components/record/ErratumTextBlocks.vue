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
 * text is optional (e.g. a pure addition has nothing to quote).
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
  <div class="erratum-text-blocks">
    <div v-if="originalHtml" class="erratum-block">
      <p class="text-overline mb-1">Original text — says:</p>
      <!-- eslint-disable-next-line vue/no-v-html -->
      <blockquote class="erratum-block-body" v-html="originalHtml" />
    </div>

    <div class="erratum-block">
      <p class="text-overline mb-1">Corrected text — should say:</p>
      <!-- eslint-disable-next-line vue/no-v-html -->
      <blockquote class="erratum-block-body" v-html="correctedHtml" />
    </div>

    <div v-if="notesHtml" class="erratum-block">
      <p class="text-overline mb-1">Notes</p>
      <!-- eslint-disable-next-line vue/no-v-html -->
      <div class="erratum-block-body" v-html="notesHtml" />
    </div>
  </div>
</template>

<style scoped>
.erratum-text-blocks {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.erratum-block-body {
  margin: 0;
  padding-left: 0.75rem;
  border-left: 3px solid rgba(var(--v-border-color), var(--v-border-opacity));
  overflow-wrap: break-word;
}
</style>
