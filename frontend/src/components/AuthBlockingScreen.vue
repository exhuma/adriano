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
  <div class="auth-blocking" role="alert">
    <v-icon icon="mdi-shield-alert-outline" size="48" color="error" />
    <h1 class="text-h5 mt-2">{{ title }}</h1>
    <p class="text-body-2 mt-2">{{ text }}</p>
    <div v-if="$slots.actions" class="mt-4">
      <slot name="actions" />
    </div>
  </div>
</template>

<style scoped>
.auth-blocking {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 3.5rem 1rem;
  text-align: center;
  max-width: 32rem;
  margin: 0 auto;
}
</style>
