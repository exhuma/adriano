<script setup lang="ts">
/**
 * Record detail page sidebar's relationship cards: outbound links
 * ("Related decisions") and inbound links ("Referenced by"). Errata
 * moved to the main column's errata section, since they are content
 * (not a sidebar-sized relationship list) -- see `RecordView`'s
 * `#errata` section. Heading level and list typography come from
 * `RecordSidebar`'s scoped defaults. The lists are not tab stops
 * themselves (docs/ui-review G-10); their links are. A target's raw
 * UUID (an unresolved link has no record to show a title for) is
 * shown short with copy, never as full running text (docs/ui-review
 * R-12, module-ux-principles "Technical identifiers"). The caller
 * (`useRecordDetailView`'s `sidebarInboundLinks`) already removes
 * whichever inbound link the page's lifecycle notice currently
 * states, so "Referenced by" never repeats that fact (P11-R-21).
 */
import ShortIdCopy from "@/components/record/ShortIdCopy.vue";
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
</script>

<template>
  <v-card
    v-if="outboundLinks.length > 0"
    class="mb-3"
    density="compact"
  >
    <v-card-title>Related decisions</v-card-title>
    <v-list tabindex="-1">
      <v-list-item v-for="(link, index) in outboundLinks" :key="index">
        <v-list-item-title>
          {{ linkTypeLabel(link.link_type) }}
        </v-list-item-title>
        <v-list-item-subtitle>
          <template v-if="link.target_id">
            <router-link :to="`/records/${link.target_id}`">
              {{ link.target_title ?? "Untitled" }}
            </router-link>
            <ShortIdCopy
              v-if="!link.target_title"
              :value="link.target_uuid"
              label="target UUID"
            />
          </template>
          <span
            v-else-if="link.ambiguous"
            class="text-warning d-inline-flex align-center flex-wrap ga-1"
          >
            <v-icon icon="mdi-alert" size="small" aria-hidden="true" />
            Ambiguous: matches {{ link.candidate_ids.length }} records
            <ShortIdCopy :value="link.target_uuid" label="target UUID" />
          </span>
          <span
            v-else
            class="text-medium-emphasis d-inline-flex align-center
              flex-wrap ga-1"
          >
            <v-icon icon="mdi-link-off" size="small" aria-hidden="true" />
            Missing target
            <ShortIdCopy :value="link.target_uuid" label="target UUID" />
          </span>
        </v-list-item-subtitle>
      </v-list-item>
    </v-list>
  </v-card>

  <v-card
    v-if="inboundLinks.length > 0"
    class="mb-3"
    density="compact"
  >
    <v-card-title>Referenced by</v-card-title>
    <v-list tabindex="-1">
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
  </v-card>
</template>
