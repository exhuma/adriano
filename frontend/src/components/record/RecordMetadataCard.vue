<script setup lang="ts">
/**
 * Record detail page sidebar's metadata card: UUID (shortened, with
 * the full value in a tooltip and copy-to-clipboard, per
 * module-ux-principles "Technical identifiers"), decision date, and
 * record kind. Heading level and list typography come from
 * `RecordSidebar`'s scoped defaults; the list is static content, so
 * it is not a tab stop.
 */
import { computed } from "vue";

import StatusChip from "@/components/StatusChip.vue";
import ShortIdCopy from "@/components/record/ShortIdCopy.vue";
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

const decisionDateText = computed(() => formatDate(props.decisionDate));
</script>

<template>
  <v-card class="mb-3" density="compact">
    <v-card-title>Metadata</v-card-title>
    <v-list tabindex="-1">
      <v-list-item>
        <v-list-item-title>UUID</v-list-item-title>
        <v-list-item-subtitle>
          <ShortIdCopy v-if="adrUuid" :value="adrUuid" label="UUID" />
          <span v-else>Not available (no valid UUID in this file)</span>
        </v-list-item-subtitle>
      </v-list-item>
      <v-list-item>
        <v-list-item-title>
          {{ recordKind === "erratum" ? "Report date" : "Decision date" }}
        </v-list-item-title>
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
