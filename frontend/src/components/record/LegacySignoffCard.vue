<script setup lang="ts">
/**
 * Record detail page's legacy sign-off card: historical, unverified
 * `signed-off-by` text from the document itself, explicitly not a
 * substitute for the approval workflow.
 */
defineProps<{
  /** Unverified legacy `signed-off-by` entries from the document. */
  entries: string[];
}>();
</script>

<template>
  <v-card v-if="entries.length > 0" class="mb-3" density="compact">
    <v-card-title class="text-title-medium">
      Legacy sign-off (unverified)
    </v-card-title>
    <v-card-text class="text-body-medium text-medium-emphasis">
      These values come from the legacy <code>signed-off-by</code> field in
      the document itself. They are historical, unauthenticated text, not
      a verified approval, and do not satisfy the approval policy.
    </v-card-text>
    <v-list density="compact">
      <v-list-item v-for="(entry, index) in entries" :key="index">
        {{ entry }}
      </v-list-item>
    </v-list>
  </v-card>
</template>
