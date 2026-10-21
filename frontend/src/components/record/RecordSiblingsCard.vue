<script setup lang="ts">
/**
 * Record detail page's "Other revisions" card: other published or
 * candidate rows sharing this record's identity, each with its own
 * approval-state chip ("Blocked" when that row's content cannot be
 * decided, R-02). Heading level comes from `RecordSidebar`'s
 * scoped defaults; the list is not a tab stop itself (G-10).
 * docs/ui-review "New issues" #1 (Task 14 re-verification, Phase 11
 * Task 16 follow-up): the link gets `d-inline-block py-1` so its own
 * clickable box is >=24px tall (it was only as tall as its text
 * line). It stays a real `router-link` in the list's own tab order.
 * "New issues" #2 (same follow-up): the link also had no colour
 * class, so it rendered in the browser's own link colour instead of
 * the theme; `text-primary` fixes it. Unlike `RecordLinksCard.vue`,
 * this link renders in `v-list-item`'s own default slot, not inside
 * a `v-list-item-subtitle`, so it carries no medium-emphasis
 * `opacity` to work around.
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
        <router-link
          :to="`/records/${sibling.id}`"
          class="d-inline-block py-1 text-primary"
        >
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
