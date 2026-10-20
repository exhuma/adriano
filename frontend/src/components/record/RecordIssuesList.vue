<script setup lang="ts">
/**
 * Record detail page's validation-issues card: lists stored issues
 * by severity, with the severity announced to assistive tech even
 * though it is also conveyed by icon colour.
 */
import type { IssueOut } from "@/types/records";

defineProps<{
  /** Stored validation issues for this record. */
  issues: IssueOut[];
}>();
</script>

<template>
  <v-card v-if="issues.length > 0" class="mb-4">
    <v-card-title class="text-title-large">Validation issues</v-card-title>
    <v-list density="compact">
      <v-list-item v-for="(issue, index) in issues" :key="index">
        <template #prepend>
          <v-icon
            :icon="issue.severity === 'error' ? 'mdi-alert-circle' : 'mdi-alert'"
            :color="issue.severity === 'error' ? 'error' : 'warning'"
            aria-hidden="true"
          />
        </template>
        <v-list-item-title>
          <span class="sr-only">{{ issue.severity }}: </span>{{ issue.message }}
        </v-list-item-title>
      </v-list-item>
    </v-list>
  </v-card>
</template>

<style scoped>
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
}
</style>
