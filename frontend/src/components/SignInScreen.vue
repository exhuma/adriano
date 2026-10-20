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
  <section
    aria-labelledby="sign-in-heading"
    class="sign-in d-flex flex-column align-center text-center py-14 px-4"
  >
    <v-icon icon="mdi-shield-lock-outline" size="48" color="medium-emphasis" />
    <h1
      id="sign-in-heading"
      class="text-headline-medium font-weight-medium mt-2"
    >
      Sign in to browse the decision catalog
    </h1>
    <p class="text-body-medium text-medium-emphasis">
      This catalog requires an authenticated identity to view decision
      records, trigger polling, or record approvals.
    </p>

    <div class="sign-in-actions mt-4 d-flex flex-wrap ga-3 justify-center">
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
        color="primary"
        variant="tonal"
        prepend-icon="mdi-flask-outline"
        @click="$emit('open-dev-login')"
      >
        Dev sign-in
      </v-btn>
    </div>

    <p v-if="!oidcAvailable && !devAuthAvailable" class="text-body-medium mt-4">
      No sign-in method is available in this build. Contact an
      administrator to configure an identity provider.
    </p>
  </section>
</template>

<style scoped>
/* Vuetify has no utility class for an arbitrary max-width value.
   Without a cap the heading stretches to the full page width and
   wraps badly at mid-size viewports (docs/ui-review A-01); this
   widens the previous 32rem measure just enough to fix that while
   keeping the screen narrow and centred. Layout (flex, centering,
   padding, gap) is expressed with utility classes above instead. */
.sign-in {
  max-width: 40rem;
  margin: 0 auto;
}
</style>
