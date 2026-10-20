<script setup lang="ts">
/**
 * Record detail page's rendered-document card: the main column's
 * document body. This is the only place in the app that uses
 * `v-html`, because `renderedHtml` is sanitized server-side at
 * ingest time with `nh3` before storage (see DECISIONS.md "Record
 * schema"). Titled "Decision record" or "Erratum" by the record's
 * own kind; for an erratum, a later phase swaps in a dedicated
 * `ErratumBody` here instead of this plain rendered-HTML card.
 */
import type { RecordKind } from "@/types/records";

defineProps<{
  /** Server-sanitized HTML of the document's rendered body. */
  renderedHtml: string;
  /** Whether this record is a normal decision or an erratum. */
  recordKind: RecordKind;
}>();
</script>

<template>
  <v-card class="mb-4" variant="outlined">
    <v-card-title class="text-subtitle-1">
      {{ recordKind === "erratum" ? "Erratum" : "Decision record" }}
    </v-card-title>
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
