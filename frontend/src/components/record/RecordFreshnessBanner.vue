<script setup lang="ts">
/**
 * Record detail page status banners: the "content changed while
 * reviewing" notice, the superseded-by note (an `updated_by` or
 * `obsoleted_by` inbound link), and the polling-freshness warning.
 * Combined here because all three are dismissed/shown notices about
 * whether the content being viewed is current, each independently
 * optional (compare `DivergenceBanner`, which combines two related
 * but independent warnings the same way).
 */
import { computed } from "vue";

import type { InboundLinkOut } from "@/types/records";
import { linkTypeLabel } from "@/utils/labels";

const props = defineProps<{
  /** Whether the content changed while the caller was reviewing it. */
  digestChanged: boolean;
  /** The `updated_by`/`obsoleted_by` link(s) superseding this record,
   *  or an empty array when the record is not superseded. */
  supersededBy: InboundLinkOut[];
  /** Polling-freshness warning text, or `null` to hide the banner. */
  freshnessText: string | null;
}>();

defineEmits<{
  /** Caller dismissed the "content changed" banner. */
  "close-digest-changed": [];
}>();

const supersededByLabel = computed(() =>
  props.supersededBy.length > 0 ? linkTypeLabel(props.supersededBy[0].link_type) : "",
);
</script>

<template>
  <v-alert
    v-if="digestChanged"
    type="warning"
    variant="tonal"
    icon="mdi-refresh-alert"
    closable
    class="mb-4"
    @click:close="$emit('close-digest-changed')"
  >
    The content changed while you were reviewing; review the new
    revision before deciding.
  </v-alert>

  <p v-if="supersededBy.length > 0" class="text-body-2 mb-4">
    {{ supersededByLabel }}:
    <router-link
      v-for="(link, index) in supersededBy"
      :key="link.source_id"
      :to="`/records/${link.source_id}`"
    >
      {{ link.source_title }}<span v-if="index < supersededBy.length - 1">, </span>
    </router-link>
  </p>

  <v-alert
    v-if="freshnessText"
    type="warning"
    variant="tonal"
    icon="mdi-clock-alert-outline"
    class="mb-4"
  >
    {{ freshnessText }}
  </v-alert>
</template>
