<script setup lang="ts">
/**
 * One erratum row in `ErrataSection.vue`: a status chip (Reported /
 * Verified / Rejected / …, icon and text; the neutral "Blocked"
 * when its content cannot be decided, R-02), a type chip, its section
 * (if any), who/when reported it (if known), a link to its own page,
 * and the original/corrected/notes text. A rejected erratum is
 * collapsed by default behind a toggle button with `aria-expanded`
 * (module-ux-principles accessibility), since it no longer needs a
 * reader's attention; every other state is expanded by default.
 * the not-indexed-yet fallback's "open the
 * erratum" link had no colour class, so it rendered in the browser's
 * own link colour instead of the theme; `text-primary` fixes it.
 */
import { computed, ref } from "vue";

import StatusChip from "@/components/StatusChip.vue";
import ErratumTextBlocks from "@/components/record/ErratumTextBlocks.vue";
import type { ErratumOut } from "@/types/records";
import { approvalDisplayLabel, erratumTypeLabel } from "@/utils/labels";

const props = defineProps<{
  /** One published or candidate erratum correcting the viewed record. */
  erratum: ErratumOut;
}>();

const statusLabel = computed(() =>
  approvalDisplayLabel(
    {
      state: props.erratum.approval_state,
      approvable: props.erratum.approvable,
    },
    props.erratum.kind,
    "erratum",
    props.erratum.ref,
  ),
);
const typeLabel = computed(() => erratumTypeLabel(props.erratum.type));

const isRejected = computed(() => props.erratum.approval_state === "rejected");

/** Rejected errata start collapsed; everything else starts expanded. */
const expanded = ref(!isRejected.value);

/** Unique id for the collapsible region, so the toggle button's
 *  `aria-controls` can reference it (module-ux-principles
 *  accessibility: semantic structure for assistive tech). */
const bodyId = `erratum-entry-body-${props.erratum.id}`;

function toggle(): void {
  expanded.value = !expanded.value;
}

/** "Reported by X on Y", with either half omitted when unknown, and
 *  the whole line omitted when neither is known. */
const reportedLine = computed(() => {
  const parts: string[] = [];
  if (props.erratum.reported_by) {
    parts.push(`Reported by ${props.erratum.reported_by}`);
  }
  if (props.erratum.reported_date) {
    parts.push(parts.length > 0 ? `on ${props.erratum.reported_date}` : props.erratum.reported_date);
  }
  return parts.join(" ");
});
</script>

<template>
  <li class="border rounded py-3 px-4">
    <div class="d-flex flex-wrap align-center ga-2 mb-2">
      <StatusChip v-bind="statusLabel" />
      <StatusChip v-bind="typeLabel" />
      <span v-if="erratum.section" class="text-body-medium">
        Section: {{ erratum.section }}
      </span>
      <span v-if="reportedLine" class="text-body-medium text-medium-emphasis">
        {{ reportedLine }}
      </span>
      <v-btn
        :to="`/records/${erratum.id}`"
        variant="text"
        size="small"
        color="primary"
      >
        Open erratum
      </v-btn>
      <v-btn
        v-if="isRejected"
        size="small"
        variant="text"
        :aria-expanded="expanded"
        :aria-controls="bodyId"
        @click="toggle"
      >
        {{ expanded ? "Hide details" : "Show details" }}
      </v-btn>
    </div>

    <div v-show="expanded" :id="bodyId" class="mt-2">
      <p
        v-if="!erratum.has_content"
        class="text-body-medium text-medium-emphasis"
      >
        Content not indexed yet —
        <router-link :to="`/records/${erratum.id}`" class="text-primary">
          open the erratum
        </router-link>.
      </p>
      <ErratumTextBlocks
        v-else
        :original-html="erratum.original_html"
        :corrected-html="erratum.corrected_html"
        :notes-html="erratum.notes_html"
      />
    </div>
  </li>
</template>

