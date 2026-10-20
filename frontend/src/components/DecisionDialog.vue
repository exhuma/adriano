<script setup lang="ts">
/**
 * Accept/reject dialog -- the one adapter for the decide flow
 * (module-interaction-core "Adapters across deliveries"). Owns
 * wording, confirmation UX, and focus; the actual submission lives
 * in the delivery-agnostic `useDecision` composable.
 *
 * Cancel/Escape/click-outside always close without submitting
 * (module-ux-principles "UI modes": dismiss must never mutate
 * state). A rejection additionally requires an explicit confirmation
 * checkbox, since it is the more consequential of the two actions.
 */
import { computed, ref, watch } from "vue";

import { useDecision } from "@/composables/useDecision";
import type { DecisionAction, DecisionSummaryOut } from "@/types/approval";
import type { RecordKind } from "@/types/records";

const MAX_COMMENT_LENGTH = 2000;

const props = defineProps<{
  /** Whether the dialog is open (`v-model`). */
  modelValue: boolean;
  /** Record id the decision applies to. */
  recordId: string;
  /** The action this dialog asks the reviewer to confirm. */
  action: DecisionAction;
  /** Whether the record being decided is a normal decision or an
   *  erratum; switches to the "Verify/Reject erratum" wording. */
  recordKind: RecordKind;
  /** The exact digest being decided -- shown in full so the reviewer
   *  can verify it is the content they reviewed. */
  digest: string;
}>();

const emit = defineEmits<{
  /** Open/closed state changed. */
  "update:modelValue": [value: boolean];
  /** A decision was recorded. */
  decided: [event: DecisionSummaryOut];
  /** The content changed while the dialog was open (409
   *  `digest_changed`); the caller should reload the record. */
  "digest-changed": [];
}>();

const { submitting, decide } = useDecision();

const comment = ref("");
const confirmReject = ref(false);
const errorMessage = ref<string | null>(null);
const errorHintText = ref<string | null>(null);

const isErratum = computed(() => props.recordKind === "erratum");

const actionLabel = computed(() => {
  if (props.action === "rejected") {
    return "Reject";
  }
  return isErratum.value ? "Verify" : "Accept";
});
/** The noun in "Accept/Reject/Verify this <subject>?" -- an erratum
 *  is named explicitly, since the page could otherwise be mistaken
 *  for deciding the decision it corrects. */
const subjectNoun = computed(() => (isErratum.value ? "erratum" : "content"));
const canSubmit = computed(
  () => props.action === "accepted" || confirmReject.value,
);

/** Reset the form whenever the dialog is reopened, so a previous
 *  attempt's error or comment never lingers into the next one. */
watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      comment.value = "";
      confirmReject.value = false;
      errorMessage.value = null;
      errorHintText.value = null;
    }
  },
);

function close(): void {
  emit("update:modelValue", false);
}

async function submit(): Promise<void> {
  errorMessage.value = null;
  errorHintText.value = null;
  const outcome = await decide(
    props.recordId,
    props.action,
    props.digest,
    comment.value,
  );
  if (outcome.kind === "success") {
    emit("decided", outcome.event);
    close();
    return;
  }
  if (outcome.kind === "digest_changed") {
    emit("digest-changed");
    close();
    return;
  }
  errorMessage.value = outcome.message;
  errorHintText.value = outcome.hint ?? null;
}
</script>

<template>
  <v-dialog
    :model-value="modelValue"
    max-width="520"
    @update:model-value="(value: boolean) => emit('update:modelValue', value)"
  >
    <v-card>
      <v-card-title>{{ actionLabel }} this {{ subjectNoun }}?</v-card-title>
      <v-card-text>
        <p class="text-body-2 mb-2">
          You are about to <strong>{{ actionLabel.toLowerCase() }}</strong>
          the exact content at digest:
        </p>
        <p class="mb-4">
          <code class="digest-full">{{ digest }}</code>
        </p>

        <v-alert
          v-if="errorMessage"
          type="error"
          variant="tonal"
          class="mb-4"
          role="alert"
        >
          {{ errorMessage }}
          <div v-if="errorHintText" class="text-body-2 mt-1">
            {{ errorHintText }}
          </div>
        </v-alert>

        <v-textarea
          v-model="comment"
          :label="action === 'rejected' ? 'Comment (suggested)' : 'Comment (optional)'"
          :hint="
            action === 'rejected'
              ? 'Explaining why helps the author fix the content.'
              : undefined
          "
          persistent-hint
          :counter="MAX_COMMENT_LENGTH"
          :maxlength="MAX_COMMENT_LENGTH"
          variant="outlined"
          density="comfortable"
          rows="3"
          auto-grow
        />

        <v-checkbox
          v-if="action === 'rejected'"
          v-model="confirmReject"
          class="mt-1"
          density="comfortable"
          hide-details
        >
          <template #label>
            <template v-if="isErratum">I confirm I want to reject this erratum.</template>
            <template v-else>I confirm I want to reject this exact content.</template>
          </template>
        </v-checkbox>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" :disabled="submitting" @click="close">
          Cancel
        </v-btn>
        <v-btn
          :color="action === 'rejected' ? 'error' : 'primary'"
          variant="flat"
          :loading="submitting"
          :disabled="submitting || !canSubmit"
          @click="submit"
        >
          {{ actionLabel }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<style scoped>
.digest-full {
  overflow-wrap: break-word;
  word-break: break-all;
}
</style>
