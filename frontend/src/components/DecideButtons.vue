<script setup lang="ts">
/**
 * Accept/Reject (or "Verify erratum"/"Reject erratum") buttons plus
 * the `DecisionDialog` they open. Shared by the main column's
 * `ApprovalCard` and the sidebar's `RecordApprovalSummaryCard`
 * (docs/ui-review R-01) so both places use one implementation of the
 * open-dialog and focus-return handling. Each instance owns its own
 * dialog; `v-dialog` is modal, so the other instance's buttons cannot
 * be reached while one dialog is open and two dialogs are never open
 * at once.
 */
import { ref } from "vue";

import DecisionDialog from "@/components/DecisionDialog.vue";
import type { DecisionAction, DecisionSummaryOut } from "@/types/approval";
import type { RecordKind } from "@/types/records";

defineProps<{
  /** Record id, for the decision dialog's submission. */
  recordId: string;
  /** Decision or erratum; picks the button and dialog wording. */
  recordKind: RecordKind;
  /** Title of the record being decided, passed straight through to
   *  the dialog so it can name the record (docs/ui-review D-02). */
  recordTitle: string;
  /** The exact digest being decided. */
  digest: string;
}>();

const emit = defineEmits<{
  /** A decision was recorded; the page should reload the record. */
  decided: [event: DecisionSummaryOut];
  /** The content changed while a decision was pending. */
  "digest-changed": [];
}>();

const dialogOpen = ref(false);
const dialogAction = ref<DecisionAction>("accepted");
const triggerButton = ref<HTMLElement | null>(null);

function openDialog(action: DecisionAction, event: MouseEvent): void {
  dialogAction.value = action;
  triggerButton.value = event.currentTarget as HTMLElement;
  dialogOpen.value = true;
}

function onDialogModel(open: boolean): void {
  dialogOpen.value = open;
  if (!open) {
    // Focus returns to whichever button opened the dialog, so
    // keyboard users land back where they were, not at the top of
    // the page (module-ux-principles accessibility: visible focus).
    triggerButton.value?.focus();
  }
}
</script>

<template>
  <div class="d-flex flex-wrap ga-2">
    <v-btn
      color="primary"
      variant="flat"
      prepend-icon="mdi-check"
      @click="openDialog('accepted', $event)"
    >
      {{ recordKind === "erratum" ? "Verify erratum" : "Accept" }}
    </v-btn>
    <v-btn
      color="error"
      variant="outlined"
      prepend-icon="mdi-close"
      @click="openDialog('rejected', $event)"
    >
      {{ recordKind === "erratum" ? "Reject erratum" : "Reject" }}
    </v-btn>

    <DecisionDialog
      :model-value="dialogOpen"
      :record-id="recordId"
      :action="dialogAction"
      :record-kind="recordKind"
      :record-title="recordTitle"
      :digest="digest"
      @update:model-value="onDialogModel"
      @decided="(event) => emit('decided', event)"
      @digest-changed="emit('digest-changed')"
    />
  </div>
</template>
