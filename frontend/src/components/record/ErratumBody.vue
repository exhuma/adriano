<script setup lang="ts">
/**
 * Record detail page's main-column body for an erratum (used instead
 * of `RecordDecisionCard` when `record_kind === "erratum"`): which
 * decision it corrects (once resolved), its type/section/reporter,
 * and its own original/corrected/notes text.
 */
import { computed } from "vue";

import StatusChip from "@/components/StatusChip.vue";
import ErratumTextBlocks from "@/components/record/ErratumTextBlocks.vue";
import ShortIdCopy from "@/components/record/ShortIdCopy.vue";
import type { ErratumContentOut, ErratumForOut } from "@/types/records";
import { erratumTypeLabel } from "@/utils/labels";

const props = defineProps<{
  /** This erratum's own content, or `null` when it was never
   *  indexed (e.g. a legacy row stored before erratum content was
   *  tracked). */
  erratum: ErratumContentOut | null;
  /** The decision this erratum corrects, resolved like outbound links. */
  erratumFor: ErratumForOut | null;
}>();

const typeLabel = computed(() => erratumTypeLabel(props.erratum?.type ?? null));

/** "Reported by X on Y", with either half omitted when unknown. */
const reportedLine = computed(() => {
  const parts: string[] = [];
  if (props.erratum?.reported_by) {
    parts.push(`Reported by ${props.erratum.reported_by}`);
  }
  if (props.erratum?.reported_date) {
    parts.push(parts.length > 0 ? `on ${props.erratum.reported_date}` : props.erratum.reported_date);
  }
  return parts.join(" ");
});
</script>

<template>
  <v-card class="mb-4" variant="outlined">
    <v-card-title tag="h2" class="text-subtitle-1">Erratum</v-card-title>
    <v-card-text>
      <!--
        The resolved case is shown once, as the page's own h1
        ("Erratum for <target>") -- see `RecordHeader.vue` -- so it is
        not repeated here. The unresolved case has no other home on
        the page, so it stays.
      -->
      <p v-if="erratumFor && !erratumFor.resolved" class="text-body-2 mb-3">
        Erratum for an unknown decision
        <ShortIdCopy :value="erratumFor.uuid" label="target UUID" />.
      </p>

      <template v-if="erratum">
        <div class="erratum-meta mb-3">
          <StatusChip v-bind="typeLabel" />
          <span v-if="erratum.section" class="text-body-2">
            Section: {{ erratum.section }}
          </span>
          <span v-if="reportedLine" class="text-body-2 text-medium-emphasis">
            {{ reportedLine }}
          </span>
        </div>

        <ErratumTextBlocks
          :original-html="erratum.original_html"
          :corrected-html="erratum.corrected_html"
          :notes-html="erratum.notes_html"
        />
      </template>
      <p v-else class="text-body-2 text-medium-emphasis">
        Content not indexed yet.
      </p>
    </v-card-text>
  </v-card>
</template>

<style scoped>
.erratum-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
}
</style>
