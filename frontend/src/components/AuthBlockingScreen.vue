<script setup lang="ts">
/**
 * Full-page blocking state for authentication failures that must
 * not loop into another sign-in attempt: backend auth unconfigured
 * or unreachable (503), and a re-authentication loop guard failure.
 * Announced assertively to assistive tech (`role="alert"`), unlike
 * the ordinary `ErrorState`, because the app is otherwise unusable
 * until an operator resolves the underlying configuration.
 */
defineProps<{
  /** Short heading, e.g. "Authentication is not configured". */
  title: string;
  /** Plain-language explanation and next step. */
  text: string;
}>();
</script>

<template>
  <div
    class="auth-blocking d-flex flex-column align-center text-center
      py-14 px-4 mx-auto"
    role="alert"
  >
    <v-icon
      icon="mdi-shield-alert-outline"
      size="48"
      color="error"
      aria-hidden="true"
    />
    <h1 class="text-headline-medium font-weight-medium mt-2">{{ title }}</h1>
    <p class="text-body-medium mt-2">{{ text }}</p>
    <div v-if="$slots.actions" class="mt-4">
      <slot name="actions" />
    </div>
  </div>
</template>

<style scoped>
/* Vuetify has no utility class for an arbitrary max-width value (same
   limitation noted in SignInScreen.vue); layout, padding, and
   centering move to utility classes above. */
.auth-blocking {
  max-width: 32rem;
}
</style>
