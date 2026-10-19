<script setup lang="ts">
/**
 * Record detail page's "Other revisions" card: other published or
 * candidate rows sharing this record's identity, each with its own
 * approval-state chip.
 */
import StatusChip from "@/components/StatusChip.vue";
import type { SiblingOut } from "@/types/records";
import { approvalStateLabel } from "@/utils/labels";

defineProps<{
  /** Other published/candidate rows sharing this record's identity. */
  siblings: SiblingOut[];
}>();
</script>

<template>
  <v-card v-if="siblings.length > 0" class="mb-4" variant="outlined">
    <v-card-title class="text-subtitle-1">Other revisions</v-card-title>
    <v-list density="compact">
      <v-list-item v-for="sibling in siblings" :key="sibling.id">
        <router-link :to="`/records/${sibling.id}`">
          {{ sibling.title }}
        </router-link>
        <template #append>
          <StatusChip
            v-bind="approvalStateLabel(sibling.approval_state, sibling.kind)"
          />
        </template>
      </v-list-item>
    </v-list>
  </v-card>
</template>
