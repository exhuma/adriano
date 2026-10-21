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
 * docs/ui-review "New issues" #1 (Task 14 re-verification, Phase 11
 * Task 16 follow-up): each link got `d-inline-block py-1` so its own
 * clickable box is >=24px tall -- `.v-list-item-subtitle`'s
 * `line-height: 1rem` left the link only as tall as its 16px text
 * line (measured 186x16). The link stays a real `<a>`/`router-link`
 * in the list's own tab order (only the `<v-list>` itself is
 * `tabindex="-1"`, G-10), so no accessible name or focus order
 * changed.
 * docs/ui-review "New issues" #2 (same follow-up): each link also
 * had no colour class, so it rendered in the browser's own link
 * colour instead of the theme (4.14:1 in dark). `text-primary` fixes
 * that, but `.v-list-item-subtitle` renders at
 * `--v-medium-emphasis-opacity` (an element-level CSS `opacity`,
 * which composites its *whole* subtree against the backdrop, not a
 * `color-mix` any one descendant's own `color` could simply
 * override) -- left alone, that would refade `text-primary` back
 * under 4.5:1 in light (measured 2.92:1). Vuetify's own
 * `--v-list-item-subtitle-opacity` CSS variable (read by that same
 * rule, see `plugins/vuetify.ts`'s P11-R-03 comment) is the ladder's
 * hook for overriding it per-instance, set inline to `1` only on the
 * subtitle rows that actually hold this link -- the ambiguous/
 * missing-target rows keep the default fade, unchanged.
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
        <v-list-item-subtitle
          :style="
            link.target_id ? '--v-list-item-subtitle-opacity: 1' : undefined
          "
        >
          <template v-if="link.target_id">
            <span class="d-inline-flex align-center flex-wrap ga-1">
              <router-link
                :to="`/records/${link.target_id}`"
                class="d-inline-block py-1 text-primary"
              >
                {{ link.target_title ?? "Untitled" }}
              </router-link>
              <ShortIdCopy
                v-if="!link.target_title"
                :value="link.target_uuid"
                label="target UUID"
              />
            </span>
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
        <v-list-item-subtitle style="--v-list-item-subtitle-opacity: 1">
          <router-link
            :to="`/records/${link.source_id}`"
            class="d-inline-block py-1 text-primary"
          >
            {{ link.source_title }}
          </router-link>
        </v-list-item-subtitle>
      </v-list-item>
    </v-list>
  </v-card>
</template>
