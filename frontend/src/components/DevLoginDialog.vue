<script setup lang="ts">
/**
 * Dev-only sign-in dialog: mints an HS256 token for a hand-picked
 * identity via `POST /auth/dev/token`. Only ever rendered when
 * `devAuthEnabled` is true (`src/config.ts`) -- the parent is
 * responsible for that gate so this component never has to repeat
 * it.
 *
 * Cancel/Escape/click-outside all close the dialog without minting a
 * token or touching any existing session (module-ux-principles "UI
 * modes": dismiss must never mutate state).
 */
import { ref, useId, watch } from "vue";

import { ApiError } from "@/api";
import { devSignIn } from "@/auth/devAuth";

/** One-click role preset, matching this catalog's documented
 *  example `rbac`/`approval_policy` role names (DECISIONS.md); real
 *  deployments may use different names, in which case the roles
 *  field below can still be edited by hand. */
interface RolePreset {
  label: string;
  roles: string[];
}

const PRESETS: RolePreset[] = [
  { label: "Reader", roles: ["reader"] },
  { label: "Operator/Admin", roles: ["admin"] },
  { label: "Reviewer", roles: ["adr-reviewer"] },
];

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

/** Id of the heading, referenced by the dialog's own
 *  `aria-labelledby` so assistive tech announces it as the dialog's
 *  accessible name instead of an unnamed "dialog" (docs/ui-review
 *  D-01). */
const titleId = useId();

/** docs/ui-review D-03: see `DecisionDialog.vue` for why this is a
 *  scoped `v-defaults-provider` instead of a global `VCardText`
 *  default. */
const dialogCardDefaults = {
  VCardTitle: { class: "ma-0 px-6" },
  VCardText: { class: "px-6" },
} as const;

/** Reset the form whenever the dialog is reopened, so a previous
 *  submission's error never lingers into the next attempt. */
watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      errorText.value = null;
      submitting.value = false;
    }
  },
);

function applyPreset(preset: RolePreset): void {
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
    @update:model-value="(value: boolean) => emit('update:modelValue', value)"
  >
    <v-defaults-provider :defaults="dialogCardDefaults">
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
            v-model="sub"
            label="Subject (sub)"
            hint="Any stable identifier, e.g. a username."
            persistent-hint
            variant="outlined"
            density="comfortable"
            class="mb-2"
            autofocus
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

          <div class="presets mt-3" role="group" aria-label="Role presets">
            <v-btn
              v-for="preset in PRESETS"
              :key="preset.label"
              size="small"
              variant="tonal"
              class="mr-2 mb-2"
              @click="applyPreset(preset)"
            >
              {{ preset.label }}
            </v-btn>
          </div>
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
    </v-defaults-provider>
  </v-dialog>
</template>
