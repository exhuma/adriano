<script setup lang="ts">
/**
 * Application shell: app bar with navigation, auth status, and
 * backend status; the mandatory page-loading indicator; and the
 * routed view -- gated behind an authenticated session except for
 * the OIDC callback route (which is how sign-in completes) and the
 * blocking states below.
 */
import { computed, defineAsyncComponent, ref } from "vue";
import { useRoute } from "vue-router";

import AuthBlockingScreen from "@/components/AuthBlockingScreen.vue";
import SignInScreen from "@/components/SignInScreen.vue";
import StatusChip from "@/components/StatusChip.vue";
import { devAuthEnabled } from "@/config";
import { useAuth } from "@/composables/useAuth";
import { useHealth } from "@/composables/useHealth";
import { isLoading } from "@/composables/useLoading";

// `DevLoginDialog` (and everything it pulls in: `src/auth/devAuth.ts`,
// `src/api/devAuth.ts`, and the `/auth/dev/token` endpoint path) is
// loaded through a dynamic `import()` gated by the *same literal
// expression* `src/config.ts` uses for `devAuthEnabled`, written out
// again here rather than referencing that import: Vite/esbuild
// replace `import.meta.env.DEV`/`import.meta.env.VITE_DEV_AUTH`
// textually in *this* module at build time, so in a production build
// the condition below is literally `false` and the bundler's
// dead-code elimination drops the `import()` call -- and therefore
// the whole dev-login chunk -- rather than merely leaving it
// unreached at runtime (`module-dev-auth-bypass`). Relying on the
// imported `devAuthEnabled` boolean here instead would require the
// minifier to propagate that constant across a module boundary,
// which is not guaranteed; `scripts/check-no-dev-auth.sh` proves
// this works by grepping the built `dist/` for dev-login markers.
const DevLoginDialog =
  import.meta.env.DEV && import.meta.env.VITE_DEV_AUTH === "true"
    ? defineAsyncComponent(() => import("@/components/DevLoginDialog.vue"))
    : null;

const route = useRoute();
const { state: healthState, payload: healthPayload, check: recheckHealth } = useHealth();

const {
  me,
  meError,
  authMode,
  authError,
  oidcConfigured,
  initAuth,
  signInWithOidc,
  signOut,
} = useAuth();

initAuth();

const devDialogOpen = ref(false);

/** The OIDC callback route handles sign-in itself and must render
 *  regardless of auth state -- it is how sign-in completes. */
const isCallbackRoute = computed(() => route.name === "auth-callback");

/** `/healthz` reports the backend cannot authenticate anyone at all
 *  (no OIDC and no dev secret configured) -- distinct from "nobody
 *  has signed in yet": nobody *can*. */
const authUnconfigured = computed(
  () => healthState.value !== "checking" && healthPayload.value?.auth === "unconfigured",
);

const signedIn = computed(() => me.value !== null);

const unconfiguredText = computed(() =>
  meError.value?.kind === "unavailable"
    ? meError.value.detail
    : "This deployment has no identity provider and no dev-auth secret " +
        "configured, so nobody can sign in. An administrator must set " +
        "ADRIANO_OIDC_AUTHORITY or the dev-only ADRIANO_DEV_SHARED_SECRET " +
        "(never in production).",
);

const hasConfigProblem = computed(() => {
  const payload = healthPayload.value;
  if (!payload) {
    return false;
  }
  const configProblem = payload.config !== undefined && payload.config !== "ok";
  const policyProblem =
    payload.policy !== undefined && payload.policy !== "configured";
  return configProblem || policyProblem;
});

const healthChip = computed(() => {
  switch (healthState.value) {
    case "ok":
      return { icon: "mdi-check-circle", text: "Backend online", color: "success" };
    case "degraded":
      return {
        icon: "mdi-alert-circle",
        text: "Backend degraded",
        color: "warning",
      };
    case "error":
      return {
        icon: "mdi-close-circle",
        text: "Backend unreachable",
        color: "error",
      };
    default:
      return { icon: "mdi-dots-horizontal", text: "Checking…", color: undefined };
  }
});

async function handleSignOut(): Promise<void> {
  await signOut();
}
</script>

<template>
  <v-app>
    <a class="skip-link" href="#main-content">Skip to main content</a>

    <v-app-bar :elevation="1">
      <v-app-bar-title>adriano</v-app-bar-title>

      <template v-if="signedIn || isCallbackRoute">
        <v-btn to="/" variant="text">Catalog</v-btn>
        <v-btn to="/sources" variant="text">Sources</v-btn>
      </template>

      <v-spacer />

      <!--
        Mode indicator for an active dev-login session
        (module-ux-principles "UI modes"): always expanded, never
        hidden behind a hover or an overflow menu, states what is in
        effect. `role="status" aria-live="polite"` on the wrapper so
        entering/leaving the mode is announced, not just shown.
      -->
      <span
        v-if="authMode === 'dev'"
        role="status"
        aria-live="polite"
        class="mr-4"
      >
        <StatusChip icon="mdi-flask-outline" text="DEV LOGIN" color="warning" />
      </span>

      <router-link
        v-if="hasConfigProblem"
        to="/sources"
        class="mr-4 config-warning-link"
        aria-label="Configuration issue detected; go to Sources for details"
      >
        <StatusChip
          icon="mdi-cog-outline"
          text="Configuration issue"
          color="warning"
        />
      </router-link>

      <StatusChip
        :icon="healthChip.icon"
        :text="healthChip.text"
        :color="healthChip.color"
        class="mr-4"
      />

      <span v-if="signedIn" class="mr-2 text-body-2 d-none d-sm-inline">
        {{ me!.display }}
      </span>
      <v-btn v-if="signedIn" variant="text" prepend-icon="mdi-logout" @click="handleSignOut">
        Sign out
      </v-btn>

      <v-progress-linear
        v-if="isLoading"
        absolute
        color="primary"
        indeterminate
        location="bottom"
      />
    </v-app-bar>

    <v-main>
      <v-container id="main-content" tabindex="-1">
        <router-view v-if="isCallbackRoute" />

        <AuthBlockingScreen
          v-else-if="authError"
          title="Sign-in could not be completed"
          :text="authError"
        >
          <template #actions>
            <v-btn color="primary" variant="tonal" @click="handleSignOut">
              Sign out and try again
            </v-btn>
          </template>
        </AuthBlockingScreen>

        <AuthBlockingScreen
          v-else-if="authUnconfigured || meError?.kind === 'unavailable'"
          title="Authentication is not configured"
          :text="unconfiguredText"
        >
          <template #actions>
            <v-btn variant="tonal" prepend-icon="mdi-refresh" @click="recheckHealth">
              Check again
            </v-btn>
          </template>
        </AuthBlockingScreen>

        <SignInScreen
          v-else-if="!signedIn"
          :oidc-available="oidcConfigured"
          :dev-auth-available="devAuthEnabled"
          @sign-in-oidc="signInWithOidc"
          @open-dev-login="devDialogOpen = true"
        />

        <router-view v-else />
      </v-container>
    </v-main>

    <component
      :is="DevLoginDialog"
      v-if="DevLoginDialog"
      v-model="devDialogOpen"
    />
  </v-app>
</template>

<style scoped>
.skip-link {
  position: absolute;
  top: -40px;
  left: 0;
  background: rgb(var(--v-theme-primary));
  color: rgb(var(--v-theme-on-primary));
  padding: 0.5rem 1rem;
  z-index: 100;
}

.skip-link:focus {
  top: 0;
}

.config-warning-link {
  text-decoration: none;
}
</style>
