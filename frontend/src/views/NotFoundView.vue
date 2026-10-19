<script setup lang="ts">
/** 404 fallback for unmatched routes. */
</script>

<template>
  <section aria-labelledby="not-found-heading" class="not-found">
    <v-icon icon="mdi-compass-off-outline" size="48" color="medium-emphasis" />
    <h1 id="not-found-heading" class="text-h5 mt-2">Page not found</h1>
    <p class="text-body-2 text-medium-emphasis">
      The page you are looking for does not exist.
    </p>
    <v-btn class="mt-4" color="primary" variant="tonal" to="/">
      Back to search
    </v-btn>
  </section>
</template>

<style scoped>
.not-found {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 3rem 1rem;
  text-align: center;
}
</style>
