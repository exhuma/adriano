<script setup lang="ts">
/**
 * Dev-only sign-in dialog: mints an HS256 token for a hand-picked
 * identity via `POST /auth/dev/token`. Its role presets (Reader,
 * Reviewer, Operator) come from the loaded catalog via
 * `GET /auth/dev/roles` (see `src/auth/devPresets.ts`); presets the
 * catalog cannot satisfy are not shown, and the roles field can
 * always be typed by hand (docs/ui-review D-04). Only ever rendered when
 * `devAuthEnabled` is true (`src/config.ts`) -- the parent is
 * responsible for that gate so this component never has to repeat
 * it.
 *
 * Cancel/Escape/click-outside all close the dialog without minting a
 * token or touching any existing session (module-ux-principles "UI
 * modes": dismiss must never mutate state).
 */
import { ref, useId, watch } from "vue";
import type { VTextField } from "vuetify/components";

import { ApiError } from "@/api";
import {
  devSignIn,
  loadDevPresets,
  type DevRolePreset,
} from "@/auth/devAuth";

const props = defineProps<{
  /** Whether the dialog is open (`v-model`). */
  modelValue: boolean;
}>();

const emit = defineEmits<{
  /** Open/closed state changed (Cancel, Escape, click-outside, or a
   *  successful sign-in all close it this way). */
  "update:modelValue": [value: boolean];
  /** A dev token was minted and `/me` loaded successfully. */
  "signed-in": [];
}>();

const sub = ref("");
const name = ref("");
const email = ref("");
const roles = ref("");
const submitting = ref(false);
const errorText = ref<string | null>(null);

/** Presets derived from this catalog's roles; empty while loading
 *  and after a failed fetch, so manual entry still works. */
const presets = ref<DevRolePreset[]>([]);
/** Whether the role list could not be fetched (shown as a short,
 *  non-blocking note; manual entry still works). */
const presetsFailed = ref(false);
/** Guards against a slow, superseded preset fetch overwriting a
 *  newer one when the dialog is reopened quickly. */
let presetRequest = 0;

async function refreshPresets(): Promise<void> {
  const request = ++presetRequest;
  presets.value = [];
  presetsFailed.value = false;
  try {
    const loaded = await loadDevPresets();
    if (request === presetRequest) {
      presets.value = loaded;
    }
  } catch {
    if (request === presetRequest) {
      presetsFailed.value = true;
    }
  }
}

/** Id of the heading, referenced by the dialog's own
 *  `aria-labelledby` so assistive tech announces it as the dialog's
 *  accessible name instead of an unnamed "dialog" (docs/ui-review
 *  D-01). */
const titleId = useId();

/** Reset the form whenever the dialog is reopened, so a previous
 *  submission's error never lingers into the next attempt, and
 *  re-read the catalog's roles (the backend may have restarted with
 *  a different catalog). */
watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      errorText.value = null;
      submitting.value = false;
      void refreshPresets();
    }
  },
  { immediate: true },
);

/** The Subject field, focused once per open (see `focusSubject`). */
const subjectField = ref<InstanceType<typeof VTextField> | null>(null);

/** Move focus to Subject once the open transition has finished.
 *
 *  Deliberately not the field's `autofocus` prop: Vuetify implements
 *  that with an IntersectionObserver that re-fires (50 ms later)
 *  whenever the field's intersection changes -- e.g. when the preset
 *  buttons appear after the role fetch resolves and the dialog grows
 *  -- which stole focus from the Roles field mid-typing and sent
 *  roles into Subject. `after-enter` fires exactly once per open. */
function focusSubject(): void {
  subjectField.value?.focus();
}

function applyPreset(preset: DevRolePreset): void {
  roles.value = preset.roles.join(", ");
}

function parsedRoles(): string[] {
  return roles.value
    .split(",")
    .map((role) => role.trim())
    .filter((role) => role.length > 0);
}

function close(): void {
  emit("update:modelValue", false);
}

async function submit(): Promise<void> {
  if (!sub.value.trim()) {
    errorText.value = "Enter a subject identifier.";
    return;
  }
  submitting.value = true;
  errorText.value = null;
  try {
    await devSignIn({
      sub: sub.value.trim(),
      name: name.value.trim() || undefined,
      email: email.value.trim() || undefined,
      roles: parsedRoles(),
    });
    emit("signed-in");
    close();
  } catch (error) {
    if (error instanceof ApiError && error.status === 503) {
      errorText.value =
        "Dev login is not available: the backend has no " +
        "ADRIANO_DEV_SHARED_SECRET configured.";
    } else {
      errorText.value = "Could not sign in. Check the fields and try again.";
    }
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <v-dialog
    :model-value="modelValue"
    :aria-labelledby="titleId"
    max-width="480"
    @after-enter="focusSubject"
    @update:model-value="(value: boolean) => emit('update:modelValue', value)"
  >
    <v-card>
      <v-card-title :id="titleId" tag="h2" class="text-title-large">
        Dev sign-in
      </v-card-title>
      <v-card-subtitle>
        Local-only: mints a token for any identity you type. Never
        available in a production build.
      </v-card-subtitle>
      <v-card-text>
        <v-alert
          v-if="errorText"
          type="error"
          variant="tonal"
          class="mb-4"
          role="alert"
        >
          {{ errorText }}
        </v-alert>

        <v-text-field
          ref="subjectField"
          v-model="sub"
          label="Subject (sub)"
          hint="Any stable identifier, e.g. a username."
          persistent-hint
          variant="outlined"
          density="comfortable"
          class="mb-2"
        />
        <v-text-field
          v-model="name"
          label="Display name (optional)"
          variant="outlined"
          density="comfortable"
          class="mb-2"
        />
        <v-text-field
          v-model="email"
          label="Email (optional)"
          variant="outlined"
          density="comfortable"
          class="mb-2"
        />
        <v-text-field
          v-model="roles"
          label="Roles (comma-separated)"
          :hint="
            `Must match role names in this catalog's ` +
              `rbac/approval_policy configuration.`
          "
          persistent-hint
          variant="outlined"
          density="comfortable"
        />

        <div
          v-if="presets.length"
          class="mt-3"
          role="group"
          aria-label="Role presets"
        >
          <v-btn
            v-for="preset in presets"
            :key="preset.label"
            :title="preset.roles.join(', ')"
            size="small"
            variant="tonal"
            class="mr-2 mb-2"
            @click="applyPreset(preset)"
          >
            {{ preset.label }}
          </v-btn>
        </div>
        <p
          v-else-if="presetsFailed"
          class="mt-3 text-body-small text-medium-emphasis"
        >
          Could not load this catalog's roles. Type them by hand.
        </p>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="close">Cancel</v-btn>
        <v-btn
          color="primary"
          variant="flat"
          :loading="submitting"
          :disabled="submitting"
          @click="submit"
        >
          Sign in
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
