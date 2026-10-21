<script setup lang="ts">
/**
 * Record detail page's provenance card: source/project, path and
 * ref, source location link, and freshness (last indexed time).
 * Long values wrap rather than ending in an ellipsis, and the path
 * has a copy button. The path and its copy
 * button sit in a `d-flex align-start ga-1` row, with the path text
 * in a `text-break flex-1-1` span, so the button never wraps onto
 * its own line below the path (P11-R-20). Heading level and list
 * typography -- including the one-line clamp override -- come from
 * `RecordSidebar`'s scoped defaults; the list is static content, so
 * it is not a tab stop (G-10).
 */
import { computed } from "vue";

import CopyValueButton from "@/components/CopyValueButton.vue";
import type { FreshnessOut, ProvenanceOut } from "@/types/records";
import { formatDateTime, formatRelativeTime } from "@/utils/dates";

const props = defineProps<{
  /** Where this record's content came from. */
  provenance: ProvenanceOut;
  /** Freshness of the owning registration. */
  freshness: FreshnessOut;
}>();

const sourceUrlIsLink = computed(() => {
  const url = props.provenance.source_url;
  return Boolean(url && /^https?:\/\//.test(url));
});
</script>

<template>
  <v-card class="mb-3" density="compact">
    <v-card-title>Provenance</v-card-title>
    <v-list tabindex="-1">
      <v-list-item>
        <v-list-item-title>Source</v-list-item-title>
        <v-list-item-subtitle class="text-break">
          {{ provenance.source_id }} / {{ provenance.project }}
        </v-list-item-subtitle>
      </v-list-item>
      <v-list-item>
        <v-list-item-title>Path &amp; ref</v-list-item-title>
        <v-list-item-subtitle class="d-flex align-start ga-1">
          <span class="text-break flex-1-1">
            {{ provenance.path }} @ {{ provenance.ref }}
          </span>
          <CopyValueButton :value="provenance.path" label="file path" />
        </v-list-item-subtitle>
      </v-list-item>
      <v-list-item>
        <v-list-item-title>Source location</v-list-item-title>
        <v-list-item-subtitle class="text-break">
          <a
            v-if="sourceUrlIsLink"
            :href="provenance.source_url!"
            target="_blank"
            rel="noopener"
          >
            View source
            <v-icon icon="mdi-open-in-new" size="small" aria-hidden="true" />
          </a>
          <span v-else-if="provenance.source_url">
            {{ provenance.source_url }}
          </span>
          <span v-else>Not available</span>
        </v-list-item-subtitle>
      </v-list-item>
      <v-list-item>
        <v-list-item-title>Freshness</v-list-item-title>
        <v-list-item-subtitle>
          Last indexed
          {{ formatRelativeTime(freshness.last_success_at) ?? "never" }}
          <span v-if="freshness.last_success_at">
            ({{ formatDateTime(freshness.last_success_at) }})
          </span>
        </v-list-item-subtitle>
      </v-list-item>
    </v-list>
  </v-card>
</template>
