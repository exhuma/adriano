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
import type { ErratumContentOut, ErratumForOut } from "@/types/records";
import { shortUuid } from "@/utils/digest";
import { erratumTypeLabel } from "@/utils/labels";

const props = defineProps<{
  /** This erratum's own content, or `null` if somehow missing. */
  erratum: ErratumContentOut | null;
  /** The decision this erratum corrects, resolved like outbound links. */
  erratumFor: ErratumForOut | null;
}>();

const typeLabel = computed(() => erratumTypeLabel(props.erratum?.type ?? null));

/** Short form of the target UUID, shown when it cannot be resolved
 *  to a known record; the caller must keep the full value reachable
 *  elsewhere (module-ux-principles "Technical identifiers"). */
const erratumForShortUuid = computed(() =>
  props.erratumFor ? shortUuid(props.erratumFor.uuid) : "",
);

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
    <v-card-title class="text-subtitle-1">Erratum</v-card-title>
    <v-card-text>
      <p v-if="erratumFor" class="text-body-2 mb-3">
        <template v-if="erratumFor.resolved && erratumFor.id">
          Erratum for
          <router-link :to="`/records/${erratumFor.id}`">{{ erratumFor.title }}</router-link>.
        </template>
        <template v-else>
          Erratum for an unknown decision <code>{{ erratumForShortUuid }}</code>.
        </template>
      </p>

      <div class="erratum-meta mb-3">
        <StatusChip v-bind="typeLabel" />
        <span v-if="erratum?.section" class="text-body-2">
          Section: {{ erratum.section }}
        </span>
        <span v-if="reportedLine" class="text-body-2 text-medium-emphasis">
          {{ reportedLine }}
        </span>
      </div>

      <ErratumTextBlocks
        v-if="erratum"
        :original-html="erratum.original_html"
        :corrected-html="erratum.corrected_html"
        :notes-html="erratum.notes_html"
      />
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
