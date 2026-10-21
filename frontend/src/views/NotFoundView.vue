<script setup lang="ts">
/** 404 fallback for unmatched routes. */
</script>

<template>
  <section
    aria-labelledby="not-found-heading"
    class="not-found d-flex flex-column align-center text-center py-12 px-4"
  >
    <v-icon
      icon="mdi-compass-off-outline"
      size="48"
      color="medium-emphasis"
      aria-hidden="true"
    />
    <h1
      id="not-found-heading"
      class="text-headline-medium font-weight-medium mt-2"
    >
      Page not found
    </h1>
    <p class="text-body-medium text-medium-emphasis">
      The page you are looking for does not exist.
    </p>
    <v-btn class="mt-4" color="primary" variant="tonal" to="/">
      Back to search
    </v-btn>
  </section>
</template>

