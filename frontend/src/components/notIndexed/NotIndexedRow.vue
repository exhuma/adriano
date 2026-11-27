<script setup lang="ts">
/**
 * One not-indexed entry in the list: where the file is, how it was
 * found, why it was not indexed, when it was first and last seen, and
 * the links to follow. A `v-card` per entry (not a bare list), so no
 * marker/indent CSS is needed. The relative times carry the absolute
 * time as their tooltip text, like the Sources page.
 */
import StatusChip from "@/components/StatusChip.vue";
import NotIndexedLinks from "@/components/notIndexed/NotIndexedLinks.vue";
import NotIndexedReasons from "@/components/notIndexed/NotIndexedReasons.vue";
import type { NotIndexedItem } from "@/types/notIndexed";
import { formatDateTime, formatRelativeTime } from "@/utils/dates";
import { originLabel } from "@/utils/labels";
import { notIndexedEntryLocation } from "@/utils/notIndexedPaths";

defineProps<{
  /** The entry to render. */
  item: NotIndexedItem;
}>();
</script>

<template>
  <v-card class="mb-3" variant="outlined">
    <v-card-title tag="h2" class="text-title-medium text-wrap">
      {{ item.path }}
    </v-card-title>
    <v-card-subtitle class="text-wrap">
      {{ item.source_id }} / {{ item.project }} @ {{ item.ref }}
    </v-card-subtitle>
    <v-card-text class="d-flex flex-column ga-2">
      <div class="d-flex flex-wrap align-center ga-2">
        <StatusChip
          :icon="item.origin === 'push' ? 'mdi-upload' : 'mdi-cloud-sync-outline'"
          :text="originLabel(item.origin)"
        />
        <span class="text-body-small text-medium-emphasis">
          First seen
          <span :title="formatDateTime(item.first_seen_at) ?? undefined">
            {{ formatRelativeTime(item.first_seen_at) }}
          </span>
          · last seen
          <span :title="formatDateTime(item.last_seen_at) ?? undefined">
            {{ formatRelativeTime(item.last_seen_at) }}
          </span>
        </span>
      </div>
      <NotIndexedReasons :reasons="item.reasons" />
    </v-card-text>
    <v-card-actions>
      <NotIndexedLinks
        :source-url="item.source_url"
        :holder-uuid="item.holder_uuid"
      />
      <v-spacer />
      <v-btn
        :to="notIndexedEntryLocation(item)"
        variant="tonal"
        size="small"
        color="primary"
      >
        Show details
      </v-btn>
    </v-card-actions>
  </v-card>
</template>
