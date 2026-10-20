<script setup lang="ts">
/**
 * Error placeholder with an actionable retry control
 * (module-ux-principles "Error prevention & recovery"). Announced
 * assertively to assistive tech via `role="alert"`.
 */
defineProps<{
  /** Short heading, e.g. "Couldn't load records". */
  title: string;
  /** Human-readable detail about what went wrong, when known. */
  text?: string;
}>();

defineEmits<{
  /** User activated the retry button. */
  retry: [];
}>();
</script>

<template>
  <div class="error-state" role="alert">
    <v-icon icon="mdi-alert-circle-outline" size="48" color="error" />
    <p class="text-title-large mt-2">{{ title }}</p>
    <p v-if="text" class="text-body-medium text-medium-emphasis">{{ text }}</p>
    <v-btn
      class="mt-4"
      color="primary"
      variant="tonal"
      prepend-icon="mdi-refresh"
      @click="$emit('retry')"
    >
      Retry
    </v-btn>
  </div>
</template>

<style scoped>
.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 2.5rem 1rem;
  text-align: center;
}
</style>
