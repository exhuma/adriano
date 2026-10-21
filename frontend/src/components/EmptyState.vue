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
  <div
    class="empty-state d-flex flex-column align-center text-center
      py-10 px-4"
  >
    <v-icon
      :icon="icon ?? 'mdi-inbox-outline'"
      size="48"
      color="medium-emphasis"
      aria-hidden="true"
    />
    <h2 class="text-title-large font-weight-regular mt-2 mb-0">{{ title }}</h2>
    <p v-if="text" class="text-body-medium text-medium-emphasis">{{ text }}</p>
    <div v-if="$slots.actions" class="mt-4">
      <slot name="actions" />
    </div>
  </div>
</template>

