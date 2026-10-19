<script setup lang="ts">
/**
 * Record detail page's metadata card: UUID (with copy-to-clipboard),
 * decision date, and record kind.
 */
import { computed, ref } from "vue";

import StatusChip from "@/components/StatusChip.vue";
import type { RecordKind } from "@/types/records";
import { formatDate } from "@/utils/dates";

const props = defineProps<{
  /** Canonical ADR UUID, or `null`/absent when the file has none. */
  adrUuid: string | null;
  /** Authored decision date, `YYYY-MM-DD`. */
  decisionDate: string | null;
  /** Whether `decisionDate` was inferred from the filename. */
  decisionDateInferred: boolean;
  /** Whether this record is a normal decision or an erratum. */
  recordKind: RecordKind;
}>();

const copied = ref(false);

const decisionDateText = computed(() => formatDate(props.decisionDate));

/** Copy the ADR UUID to the clipboard, with a brief "Copied!" note. */
async function copyUuid(): Promise<void> {
  if (!props.adrUuid) {
    return;
  }
  try {
    await navigator.clipboard.writeText(props.adrUuid);
    copied.value = true;
    setTimeout(() => {
      copied.value = false;
    }, 2000);
  } catch {
    // Clipboard API unavailable (e.g. insecure context); the UUID is
    // already visible as selectable text, so this is a soft failure.
  }
}
</script>

<template>
  <v-card class="mb-4" variant="outlined">
    <v-card-title class="text-subtitle-1">Metadata</v-card-title>
    <v-list density="compact">
      <v-list-item>
        <v-list-item-title>UUID</v-list-item-title>
        <v-list-item-subtitle>
          <span v-if="adrUuid">
            <code>{{ adrUuid }}</code>
            <v-btn
              icon="mdi-content-copy"
              size="x-small"
              variant="text"
              :aria-label="copied ? 'Copied UUID to clipboard' : 'Copy UUID to clipboard'"
              @click="copyUuid"
            />
            <span v-if="copied" class="text-success">Copied!</span>
          </span>
          <span v-else>Not available (no valid UUID in this file)</span>
        </v-list-item-subtitle>
      </v-list-item>
      <v-list-item>
        <v-list-item-title>Decision date</v-list-item-title>
        <v-list-item-subtitle>
          <span v-if="decisionDateText">
            {{ decisionDateText }}
            <StatusChip
              v-if="decisionDateInferred"
              icon="mdi-information-outline"
              text="Inferred from filename"
              class="ml-1"
            />
          </span>
          <span v-else>Not recorded</span>
        </v-list-item-subtitle>
      </v-list-item>
      <v-list-item>
        <v-list-item-title>Kind</v-list-item-title>
        <v-list-item-subtitle>
          {{ recordKind === "erratum" ? "Erratum" : "Decision" }}
        </v-list-item-subtitle>
      </v-list-item>
    </v-list>
  </v-card>
</template>
