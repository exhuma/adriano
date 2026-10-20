<script setup lang="ts">
/**
 * Record detail page's errata section (`#errata`, the target of
 * `RecordHeader`'s "View errata" link): published errata first, then
 * a "Proposed errata" group for candidates pushed from a branch but
 * not yet merged. Hidden entirely when there are none, so the empty
 * state is simply absent rather than an empty card.
 */
import { computed } from "vue";

import ErratumEntry from "@/components/record/ErratumEntry.vue";
import type { ErratumOut } from "@/types/records";
import { errataHeadingText } from "@/utils/labels";

const props = defineProps<{
  /** Published and candidate errata correcting this record. */
  errata: ErratumOut[];
}>();

const published = computed(() => props.errata.filter((e) => e.kind === "published"));
const proposed = computed(() => props.errata.filter((e) => e.kind === "candidate"));

/** "Errata — N errata · M proposed" -- counts published errata
 *  separately from proposed (candidate) ones, matching the header
 *  link's counts (`RecordHeader`'s `errataLinkText`), so the two
 *  never contradict each other. Never shows a bare "(0)" (R-13). */
const heading = computed(() =>
  errataHeadingText(published.value.length, proposed.value.length),
);
</script>

<template>
  <section v-if="errata.length > 0" id="errata" class="mb-4">
    <h2 class="text-title-large mb-2">{{ heading }}</h2>

    <ul v-if="published.length > 0" class="erratum-list ma-0 pa-0 d-flex flex-column ga-3">
      <ErratumEntry v-for="erratum in published" :key="erratum.id" :erratum="erratum" />
    </ul>

    <template v-if="proposed.length > 0">
      <h3 class="text-title-small mt-3 mb-2">Proposed errata</h3>
      <ul class="erratum-list ma-0 pa-0 d-flex flex-column ga-3">
        <ErratumEntry v-for="erratum in proposed" :key="erratum.id" :erratum="erratum" />
      </ul>
    </template>
  </section>
</template>

<style scoped>
.erratum-list {
  /* No Vuetify utility removes list markers. */
  list-style: none;
}
</style>
