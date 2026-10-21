<script setup lang="ts">
/**
 * Record detail page's "Other revisions" card: other published or
 * candidate rows sharing this record's identity, each with its own
 * approval-state chip ("Blocked" when that row's content cannot be
 * decided, R-02). Heading level comes from `RecordSidebar`'s
 * scoped defaults; the list is not a tab stop itself (G-10).
 */
import StatusChip from "@/components/StatusChip.vue";
import type { SiblingOut } from "@/types/records";
import { approvalDisplayLabel } from "@/utils/labels";

defineProps<{
  /** Other published/candidate rows sharing this record's identity. */
  siblings: SiblingOut[];
}>();
</script>

<template>
  <v-card v-if="siblings.length > 0" class="mb-3" density="compact">
    <v-card-title>Other revisions</v-card-title>
    <v-list tabindex="-1">
      <v-list-item v-for="sibling in siblings" :key="sibling.id">
        <router-link :to="`/records/${sibling.id}`">
          {{ sibling.title }}
        </router-link>
        <template #append>
          <StatusChip
            v-bind="
              approvalDisplayLabel(
                {
                  state: sibling.approval_state,
                  approvable: sibling.approvable,
                },
                sibling.kind,
              )
            "
          />
        </template>
      </v-list-item>
    </v-list>
  </v-card>
</template>
