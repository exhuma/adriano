<script setup lang="ts">
/**
 * Record detail page's provenance card: source/project, path and
 * ref, source location link, and freshness (last indexed time).
 */
import { computed } from "vue";

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

/** See `RecordMetadataCard.vue`'s identical constant: scopes the
 *  field-label/value sizing fix to this card's list only. */
const fieldDefaults = {
  VListItemTitle: { class: "text-label-large" },
  VListItemSubtitle: { class: "text-body-medium" },
} as const;
</script>

<template>
  <v-card class="mb-3" density="compact">
    <v-card-title class="text-title-medium">Provenance</v-card-title>
    <v-defaults-provider :defaults="fieldDefaults">
      <v-list density="compact">
        <v-list-item>
          <v-list-item-title>Source</v-list-item-title>
          <v-list-item-subtitle>
            {{ provenance.source_id }} / {{ provenance.project }}
          </v-list-item-subtitle>
        </v-list-item>
        <v-list-item>
          <v-list-item-title>Path &amp; ref</v-list-item-title>
          <v-list-item-subtitle>
            {{ provenance.path }} @ {{ provenance.ref }}
          </v-list-item-subtitle>
        </v-list-item>
        <v-list-item>
          <v-list-item-title>Source location</v-list-item-title>
          <v-list-item-subtitle>
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
    </v-defaults-provider>
  </v-card>
</template>
