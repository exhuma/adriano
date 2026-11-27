<script setup lang="ts">
/**
 * The reasons a document was not indexed, in plain words: the
 * headline for each reason code followed by the backend's own
 * message for this file. Severity is shown by icon and text colour,
 * never by colour alone.
 */
import type { IssueOut } from "@/types/records";
import { validationIssueText } from "@/utils/labels";

defineProps<{
  /** The reasons, as the API returns them. */
  reasons: IssueOut[];
}>();
</script>

<template>
  <!-- A `v-list` (not a bare `ul`) so no marker/indent CSS is needed. -->
  <v-list density="compact" bg-color="transparent" class="pa-0" :lines="false">
    <v-list-item
      v-for="(reason, index) in reasons"
      :key="`${reason.code}-${index}`"
      :prepend-icon="reason.severity === 'error' ? 'mdi-alert-circle' : 'mdi-alert'"
      class="px-0 text-body-medium"
    >
      <span class="d-sr-only">
        {{ reason.severity === "error" ? "Error:" : "Warning:" }}
      </span>
      <span class="text-wrap">
        {{ validationIssueText(reason.code, reason.message) }}
      </span>
    </v-list-item>
  </v-list>
</template>
