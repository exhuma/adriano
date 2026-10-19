<script setup lang="ts">
/**
 * Record detail page's relationship cards: outbound links ("Related
 * decisions"), inbound links ("Referenced by"), and errata. Grouped
 * together as the record's three link-shaped relationship lists,
 * each independently optional.
 */
import type { ErratumOut, InboundLinkOut, OutboundLinkOut } from "@/types/records";
import { linkTypeLabel } from "@/utils/labels";

defineProps<{
  /** Outbound `updates`/`obsoletes`/`corrects` links. */
  outboundLinks: OutboundLinkOut[];
  /** Other records linking to this one. */
  inboundLinks: InboundLinkOut[];
  /** Errata correcting this record. */
  errata: ErratumOut[];
}>();
</script>

<template>
  <v-card
    v-if="outboundLinks.length > 0"
    class="mb-4"
    variant="outlined"
  >
    <v-card-title class="text-subtitle-1">Related decisions</v-card-title>
    <v-list density="compact">
      <v-list-item v-for="(link, index) in outboundLinks" :key="index">
        <v-list-item-title>{{ linkTypeLabel(link.link_type) }}</v-list-item-title>
        <v-list-item-subtitle>
          <router-link v-if="link.target_id" :to="`/records/${link.target_id}`">
            {{ link.target_title ?? link.target_uuid }}
          </router-link>
          <span v-else-if="link.ambiguous" class="text-warning">
            <v-icon icon="mdi-alert" size="small" aria-hidden="true" />
            Ambiguous: matches {{ link.candidate_ids.length }} records
            (uuid {{ link.target_uuid }})
          </span>
          <span v-else class="text-medium-emphasis">
            <v-icon icon="mdi-link-off" size="small" aria-hidden="true" />
            Missing target (uuid {{ link.target_uuid }})
          </span>
        </v-list-item-subtitle>
      </v-list-item>
    </v-list>
  </v-card>

  <v-card
    v-if="inboundLinks.length > 0"
    class="mb-4"
    variant="outlined"
  >
    <v-card-title class="text-subtitle-1">Referenced by</v-card-title>
    <v-list density="compact">
      <v-list-item
        v-for="link in inboundLinks"
        :key="`${link.link_type}-${link.source_id}`"
      >
        <v-list-item-title>{{ linkTypeLabel(link.link_type) }}</v-list-item-title>
        <v-list-item-subtitle>
          <router-link :to="`/records/${link.source_id}`">
            {{ link.source_title }}
          </router-link>
        </v-list-item-subtitle>
      </v-list-item>
    </v-list>
  </v-card>

  <v-card v-if="errata.length > 0" class="mb-4" variant="outlined">
    <v-card-title class="text-subtitle-1">Errata</v-card-title>
    <v-list density="compact">
      <v-list-item v-for="erratum in errata" :key="erratum.id">
        <router-link :to="`/records/${erratum.id}`">{{ erratum.title }}</router-link>
      </v-list-item>
    </v-list>
  </v-card>
</template>
