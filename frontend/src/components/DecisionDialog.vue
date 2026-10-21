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
import { computed, ref, useId, watch } from "vue";

import CopyValueButton from "@/components/CopyValueButton.vue";
import { useDecision } from "@/composables/useDecision";
import type { DecisionAction, DecisionSummaryOut } from "@/types/approval";
import type { RecordKind } from "@/types/records";
import { shortDigest } from "@/utils/digest";

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
  /** Title of the record being decided, named in the dialog's own
   *  heading (docs/ui-review D-02) so a reviewer can see which
   *  record they are about to accept/reject without reading the
   *  digest. The caller (`DecideButtons`) passes through whatever
   *  the page shows as that record's title. */
  recordTitle: string;
  /** The exact digest being decided. Shown short by default with a
   *  copy button, and in full behind a disclosure, so the reviewer
   *  can still verify it is the content they reviewed (docs/ui-review
   *  R-12). */
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
const digestExpanded = ref(false);

/** Id of the heading, referenced by the dialog's own
 *  `aria-labelledby` so assistive tech announces it as the dialog's
 *  accessible name instead of an unnamed "dialog" (docs/ui-review
 *  D-01). `useId()` keeps it unique even with two `DecideButtons`
 *  instances (sidebar and main column) mounted at once. */
const titleId = useId();
/** Id of the full-digest disclosure region, referenced by the
 *  toggle button's `aria-controls`. */
const digestDisclosureId = useId();

const isErratum = computed(() => props.recordKind === "erratum");

const actionLabel = computed(() => {
  if (props.action === "rejected") {
    return "Reject";
  }
  return isErratum.value ? "Verify" : "Accept";
});
/** The noun in "the exact <subject> at digest" below the title -- an
 *  erratum is named explicitly, since the body could otherwise be
 *  mistaken for deciding the decision it corrects. The title itself
 *  (`dialogTitle`) names the record directly instead (D-02). */
const subjectNoun = computed(() => (isErratum.value ? "erratum" : "content"));
/** "Reject “Adopt gRPC for internal APIs”?" (docs/ui-review D-02):
 *  the dialog's own heading, so the record being decided is visible
 *  without reading the digest below. */
const dialogTitle = computed(
  () => `${actionLabel.value} “${props.recordTitle}”?`,
);
const canSubmit = computed(
  () => props.action === "accepted" || confirmReject.value,
);

/** docs/ui-review D-03: `v-card-title`/`v-card-text` do not render at
 *  equal horizontal padding by default (8px off at this dialog's
 *  width), and no global `VCardText` default exists yet to pair with
 *  Task 1's global `VCardTitle` default -- scoped here (Vuetify-first
 *  ladder step 3, `v-defaults-provider`) rather than globally, since
 *  changing every card's text padding site-wide is outside this
 *  dialog-only task. `DevLoginDialog` repeats the same two classes
 *  for the same reason. */
const dialogCardDefaults = {
  VCardTitle: { class: "ma-0 px-6" },
  VCardText: { class: "px-6" },
} as const;

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
      digestExpanded.value = false;
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
    :aria-labelledby="titleId"
    max-width="520"
    @update:model-value="(value: boolean) => emit('update:modelValue', value)"
  >
    <v-defaults-provider :defaults="dialogCardDefaults">
      <v-card>
        <v-card-title :id="titleId" tag="h2" class="text-title-large">
          {{ dialogTitle }}
        </v-card-title>
        <v-card-text>
          <p class="text-body-medium mb-2">
            You are about to <strong>{{ actionLabel.toLowerCase() }}</strong>
            the exact {{ subjectNoun }} at digest:
          </p>
          <p class="d-flex align-center flex-wrap ga-1 mb-1">
            <code :title="digest">{{ shortDigest(digest) }}</code>
            <CopyValueButton :value="digest" label="digest" />
          </p>
          <v-btn
            variant="text"
            size="small"
            class="pl-0 mb-2"
            :aria-expanded="digestExpanded"
            :aria-controls="digestDisclosureId"
            @click="digestExpanded = !digestExpanded"
          >
            {{ digestExpanded ? "Hide full digest" : "Show full digest" }}
          </v-btn>
          <v-expand-transition>
            <p v-show="digestExpanded" :id="digestDisclosureId" class="mb-4">
              <code class="digest-full">{{ digest }}</code>
            </p>
          </v-expand-transition>

          <v-alert
            v-if="errorMessage"
            type="error"
            variant="tonal"
            class="mb-4"
            role="alert"
          >
            {{ errorMessage }}
            <div v-if="errorHintText" class="text-body-medium mt-1">
              {{ errorHintText }}
            </div>
          </v-alert>

          <v-textarea
            v-model="comment"
            :label="
              action === 'rejected'
                ? 'Comment (suggested)'
                : 'Comment (optional)'
            "
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
              <template v-if="isErratum">
                I confirm I want to reject this erratum.
              </template>
              <template v-else>
                I confirm I want to reject this exact content.
              </template>
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
    </v-defaults-provider>
  </v-dialog>
</template>

<style scoped>
.digest-full {
  overflow-wrap: break-word;
  word-break: break-all;
}
</style>
