<script setup lang="ts">
/**
 * Record detail page's validation-issues card: lists stored issues
 * by severity, with the severity announced to assistive tech even
 * though it is also conveyed by icon colour. Messages wrap in full
 * instead of being cut at one line (docs/ui-review R-09), and the
 * static list is not a tab stop (G-10). Each message is prefixed
 * with a plain-language headline for its stable issue code
 * (docs/ui-review R-10) -- the backend's own message is kept in
 * full afterwards, so no per-instance detail (field name, value,
 * target) is lost.
 */
import type { IssueOut } from "@/types/records";
import { validationIssueText } from "@/utils/labels";

defineProps<{
  /** Stored validation issues for this record. */
  issues: IssueOut[];
}>();
</script>

<template>
  <v-card v-if="issues.length > 0" class="mb-4">
    <v-card-title tag="h2" class="text-title-large">
      Validation issues
    </v-card-title>
    <v-list density="compact" :lines="false" tabindex="-1">
      <v-list-item v-for="(issue, index) in issues" :key="index">
        <template #prepend>
          <v-icon
            :icon="issue.severity === 'error' ? 'mdi-alert-circle' : 'mdi-alert'"
            :color="issue.severity === 'error' ? 'error' : 'warning'"
            aria-hidden="true"
          />
        </template>
        <v-list-item-title class="text-wrap text-break">
          <span class="d-sr-only">{{ issue.severity }}: </span>
          {{ validationIssueText(issue.code, issue.message) }}
        </v-list-item-title>
      </v-list-item>
    </v-list>
  </v-card>
</template>
