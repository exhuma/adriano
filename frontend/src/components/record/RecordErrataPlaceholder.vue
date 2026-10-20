<script setup lang="ts">
/**
 * Minimal placeholder for the record detail page's errata section:
 * just enough (the `#errata` anchor and a title list) for
 * `RecordStatusBanners`' "View errata" link to resolve to something.
 * A later phase replaces this component with the full `ErrataSection`
 * (status chips, type/section, original vs corrected text) at the
 * same call site in `RecordView`, without moving the anchor.
 */
import type { ErratumOut } from "@/types/records";

defineProps<{
  /** Published and candidate errata correcting this record. */
  errata: ErratumOut[];
}>();
</script>

<template>
  <v-card v-if="errata.length > 0" id="errata" class="mb-4" variant="outlined">
    <v-card-title class="text-subtitle-1">Errata</v-card-title>
    <v-list density="compact">
      <v-list-item v-for="erratum in errata" :key="erratum.id">
        <router-link :to="`/records/${erratum.id}`">{{ erratum.title }}</router-link>
      </v-list-item>
    </v-list>
  </v-card>
</template>
