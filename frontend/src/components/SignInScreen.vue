<script setup lang="ts">
/**
 * Signed-out landing screen, shown instead of a broken/empty page
 * whenever there is no authenticated session yet
 * (module-ux-principles "Show explicit state").
 */
defineProps<{
  /** Whether OIDC sign-in can be offered. */
  oidcAvailable: boolean;
  /** Whether the gated dev-login entry point can be offered (always
   *  `false` in a production build; see `src/config.ts`). */
  devAuthAvailable: boolean;
}>();

defineEmits<{
  /** User chose to sign in with the configured identity provider. */
  "sign-in-oidc": [];
  /** User chose to open the dev-login dialog. */
  "open-dev-login": [];
}>();
</script>

<template>
  <section aria-labelledby="sign-in-heading" class="sign-in">
    <v-icon icon="mdi-shield-lock-outline" size="48" color="medium-emphasis" />
    <h1 id="sign-in-heading" class="text-h5 mt-2">
      Sign in to browse the decision catalog
    </h1>
    <p class="text-body-2 text-medium-emphasis">
      This catalog requires an authenticated identity to view decision
      records, trigger polling, or record approvals.
    </p>

    <div class="sign-in-actions mt-4">
      <v-btn
        v-if="oidcAvailable"
        color="primary"
        variant="flat"
        prepend-icon="mdi-login"
        @click="$emit('sign-in-oidc')"
      >
        Sign in
      </v-btn>
      <v-btn
        v-if="devAuthAvailable"
        variant="tonal"
        prepend-icon="mdi-flask-outline"
        @click="$emit('open-dev-login')"
      >
        Dev sign-in
      </v-btn>
    </div>

    <p v-if="!oidcAvailable && !devAuthAvailable" class="text-body-2 mt-4">
      No sign-in method is available in this build. Contact an
      administrator to configure an identity provider.
    </p>
  </section>
</template>

<style scoped>
.sign-in {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 3.5rem 1rem;
  text-align: center;
  max-width: 32rem;
  margin: 0 auto;
}

.sign-in-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  justify-content: center;
}
</style>
