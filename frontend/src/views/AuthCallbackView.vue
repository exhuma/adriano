<script setup lang="ts">
/**
 * OIDC redirect target (`/auth/callback`): exchanges the
 * authorization code for tokens and returns to the page the user
 * started from.
 *
 * This is always a fresh, full page load (the browser navigated away
 * to the identity provider and back), so it cannot rely on any
 * in-memory state from before the redirect -- `completeOidcCallback`
 * reads the pending request from `oidc-client-ts`'s own (session)
 * state store.
 */
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";

import { completeOidcCallback } from "@/composables/useAuth";

const router = useRouter();
const errorText = ref<string | null>(null);

onMounted(async () => {
  try {
    const returnTo = await completeOidcCallback();
    await router.replace(returnTo);
  } catch {
    errorText.value =
      "Sign-in could not be completed. The link may have expired or " +
      "already been used -- return to the app and sign in again.";
  }
});
</script>

<template>
  <section aria-labelledby="callback-heading" class="callback">
    <template v-if="errorText">
      <v-icon icon="mdi-alert-circle-outline" size="48" color="error" />
      <h1 id="callback-heading" class="text-h5 mt-2">Sign-in failed</h1>
      <p class="text-body-2 text-medium-emphasis">{{ errorText }}</p>
      <v-btn class="mt-4" color="primary" variant="tonal" to="/">
        Back to the catalog
      </v-btn>
    </template>
    <template v-else>
      <v-progress-circular indeterminate color="primary" size="32" role="status" />
      <h1 id="callback-heading" class="text-h5 mt-2">Signing you in…</h1>
    </template>
  </section>
</template>

<style scoped>
.callback {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 3rem 1rem;
  text-align: center;
}
</style>
