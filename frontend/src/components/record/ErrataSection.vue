<script setup lang="ts">
/**
 * Record detail page's errata section (`#errata`, the target of
 * `RecordStatusBanners`' "View errata" link): published errata
 * first, then a "Proposed errata" group for candidates pushed from a
 * branch but not yet merged. Hidden entirely when there are none, so
 * the empty state is simply absent rather than an empty card.
 */
import { computed } from "vue";

import ErratumEntry from "@/components/record/ErratumEntry.vue";
import type { ErratumOut } from "@/types/records";

const props = defineProps<{
  /** Published and candidate errata correcting this record. */
  errata: ErratumOut[];
}>();

const published = computed(() => props.errata.filter((e) => e.kind === "published"));
const proposed = computed(() => props.errata.filter((e) => e.kind === "candidate"));
</script>

<template>
  <section v-if="errata.length > 0" id="errata" class="mb-4">
    <h2 class="text-subtitle-1 mb-2">Errata ({{ errata.length }})</h2>

    <ul v-if="published.length > 0" class="erratum-list">
      <ErratumEntry v-for="erratum in published" :key="erratum.id" :erratum="erratum" />
    </ul>

    <template v-if="proposed.length > 0">
      <h3 class="text-subtitle-2 mt-3 mb-2">Proposed errata</h3>
      <ul class="erratum-list">
        <ErratumEntry v-for="erratum in proposed" :key="erratum.id" :erratum="erratum" />
      </ul>
    </template>
  </section>
</template>

<style scoped>
.erratum-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
</style>
