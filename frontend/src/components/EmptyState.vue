<script setup lang="ts">
/**
 * Honest "nothing here yet" placeholder. Never used to show fake or
 * sample data — callers pass the real reason the list is empty.
 */
defineProps<{
  /** Material Design Icons name shown above the message. */
  icon?: string;
  /** Short heading, e.g. "No records yet". */
  title: string;
  /** Longer explanation of why there is nothing to show. */
  text?: string;
}>();
</script>

<template>
  <div class="empty-state">
    <v-icon
      :icon="icon ?? 'mdi-inbox-outline'"
      size="48"
      color="medium-emphasis"
      aria-hidden="true"
    />
    <h2 class="text-subtitle-1 font-weight-regular mt-2 mb-0">{{ title }}</h2>
    <p v-if="text" class="text-body-2 text-medium-emphasis">{{ text }}</p>
    <div v-if="$slots.actions" class="mt-4">
      <slot name="actions" />
    </div>
  </div>
</template>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 2.5rem 1rem;
  text-align: center;
}
</style>
