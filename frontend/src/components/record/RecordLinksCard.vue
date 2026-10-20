<script setup lang="ts">
/**
 * Record detail page sidebar's relationship cards: outbound links
 * ("Related decisions") and inbound links ("Referenced by"). Errata
 * moved to the main column's errata section, since they are content
 * (not a sidebar-sized relationship list) -- see `RecordView`'s
 * `#errata` section.
 */
import type { InboundLinkOut, OutboundLinkOut } from "@/types/records";
import { linkTypeLabel } from "@/utils/labels";

defineProps<{
  /** Outbound `updates`/`obsoletes` links. An erratum's own
   *  `corrects` link is replaced by `erratum_for` and never appears
   *  here. */
  outboundLinks: OutboundLinkOut[];
  /** Other records linking to this one. */
  inboundLinks: InboundLinkOut[];
}>();

/** See `RecordMetadataCard.vue`'s identical constant: scopes the
 *  field-label/value sizing fix to these cards' lists only (the link
 *  type is the "label", the linked record's title the "value"). */
const fieldDefaults = {
  VListItemTitle: { class: "text-label-large" },
  VListItemSubtitle: { class: "text-body-medium" },
} as const;
</script>

<template>
  <v-card
    v-if="outboundLinks.length > 0"
    class="mb-3"
    density="compact"
  >
    <v-card-title class="text-title-medium">Related decisions</v-card-title>
    <v-defaults-provider :defaults="fieldDefaults">
      <v-list density="compact">
        <v-list-item v-for="(link, index) in outboundLinks" :key="index">
          <v-list-item-title>
            {{ linkTypeLabel(link.link_type) }}
          </v-list-item-title>
          <v-list-item-subtitle>
            <router-link
              v-if="link.target_id"
              :to="`/records/${link.target_id}`"
            >
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
    </v-defaults-provider>
  </v-card>

  <v-card
    v-if="inboundLinks.length > 0"
    class="mb-3"
    density="compact"
  >
    <v-card-title class="text-title-medium">Referenced by</v-card-title>
    <v-defaults-provider :defaults="fieldDefaults">
      <v-list density="compact">
        <v-list-item
          v-for="link in inboundLinks"
          :key="`${link.link_type}-${link.source_id}`"
        >
          <v-list-item-title>
            {{ linkTypeLabel(link.link_type) }}
          </v-list-item-title>
          <v-list-item-subtitle>
            <router-link :to="`/records/${link.source_id}`">
              {{ link.source_title }}
            </router-link>
          </v-list-item-subtitle>
        </v-list-item>
      </v-list>
    </v-defaults-provider>
  </v-card>
</template>
