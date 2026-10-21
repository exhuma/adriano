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
import { useDisplay } from "vuetify";

import AppBarMenu from "@/components/AppBarMenu.vue";
import AuthBlockingScreen from "@/components/AuthBlockingScreen.vue";
import SignInScreen from "@/components/SignInScreen.vue";
import StatusChip from "@/components/StatusChip.vue";
import UserMenu from "@/components/UserMenu.vue";
import { devAuthEnabled } from "@/config";
import { useAuth } from "@/composables/useAuth";
import { useHealth } from "@/composables/useHealth";
import { isLoading } from "@/composables/useLoading";
import { useThemePreference } from "@/composables/useThemePreference";

// `DevLoginDialog` (and everything it pulls in: `src/auth/devAuth.ts`,
// `src/api/devAuth.ts`, `src/auth/devPresets.ts`, and the
// `/auth/dev/token` and `/auth/dev/roles` endpoint paths) is
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

/** Vuetify breakpoint gate: on md+ the app bar shows every item
 *  inline (unchanged layout); on xs/sm everything but the product
 *  name and the mode indicator collapses into `AppBarMenu`
 *  (module-ux-principles "Fitt's/Hick's law": fewer, larger targets
 *  on a narrow viewport instead of cramped, shrinking controls). */
const { mdAndUp } = useDisplay();

// P11-R-01: apply a stored theme preference on mount, here rather
// than only inside `ThemeMenuItems` (lazily mounted inside a
// `v-menu`) -- otherwise a stored "light" choice under a dark OS
// stays dark until the user happens to open the user menu. The
// return value is unused; only the composable's apply-once side
// effect (`composables/useThemePreference.ts`) is needed here.
useThemePreference();

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

/** Product owner decision 1 (`DECISIONS.md` "Phase 11 updates";
 *  docs/ui-review G-04): the backend being healthy is the default,
 *  uninformative state, so the chip is hidden for it -- and for the
 *  transient "checking" state on first load, which is neither
 *  "degraded" nor "offline" and would otherwise flash before the
 *  first `/healthz` response. It appears only once there is
 *  something to report. */
const showHealthChip = computed(
  () => healthState.value === "degraded" || healthState.value === "error",
);

async function handleSignOut(): Promise<void> {
  await signOut();
}
</script>

<template>
  <v-app>
    <a
      class="skip-link position-absolute left-0 py-2 px-4 bg-primary"
      href="#main-content"
    >Skip to main content</a>

    <v-app-bar :elevation="1">
      <!--
        docs/ui-review G-02/G-03: wrap the bar's contents in a
        v-container with the same max-width default as `v-main`'s
        container below, so the brand, nav, and right-hand cluster
        align with the page content's edges instead of hugging the
        viewport edges. `flex-0-0` ("flex: 0 0 auto") on the title
        overrides Vuetify's `.v-toolbar-title { flex: 1 1 }` (basis
        0%, so `flex-grow-0` alone collapses it to zero width): it
        otherwise competes with `v-spacer` for leftover space, which
        is what made the nav's position drift with the signed-in
        user's display-name width -- G-02's evidence.
      -->
      <v-container class="d-flex align-center h-100">
        <v-app-bar-title class="flex-0-0 mr-2">adriano</v-app-bar-title>

        <template v-if="mdAndUp && (signedIn || isCallbackRoute)">
          <v-btn to="/" variant="text">Catalog</v-btn>
          <v-btn to="/sources" variant="text">Sources</v-btn>
        </template>

        <v-spacer />

        <!--
          Mode indicator for an active dev-login session
          (module-ux-principles "UI modes"): always expanded, never
          hidden behind a hover or an overflow menu, states what is in
          effect, on every viewport -- including xs/sm, where it is the
          only app-bar item besides the product name that stays outside
          `AppBarMenu` below. `role="status" aria-live="polite"` on the
          wrapper so entering/leaving the mode is announced, not just
          shown. Below md the label shortens to "DEV" to fit; the full
          meaning moves to `aria-label`/`title` so it is never lost.
          Colour is "info", not "warning": a dev login is a deliberate,
          reversible mode, not a fault, so it should not read as an
          alarm (docs/ui-review G-04; module-ux-principles "UI modes"
          colour rule) -- "info" still reaches 4.5:1 as chip text in
          both themes (`tests/plugins/vuetify.test.ts`).
        -->
        <span
          v-if="authMode === 'dev'"
          role="status"
          aria-live="polite"
          class="mr-4"
        >
          <StatusChip
            icon="mdi-flask-outline"
            :text="mdAndUp ? 'DEV LOGIN' : 'DEV'"
            color="info"
            :aria-label="mdAndUp ? undefined : 'DEV LOGIN: development login mode is active'"
          />
        </span>

        <template v-if="mdAndUp">
          <router-link
            v-if="hasConfigProblem"
            to="/sources"
            class="mr-4 text-decoration-none"
            aria-label="Configuration issue detected; go to Sources for details"
          >
            <StatusChip
              icon="mdi-cog-outline"
              text="Configuration issue"
              color="warning"
            />
          </router-link>

          <!--
            docs/ui-review G-04, decision 1: the chip only carries
            information when the backend is not OK, so the wrapper
            (and its `role=status` region) stays in the DOM but is
            empty while healthy, and gains the chip -- announced via
            `aria-live` -- once there is something to report.
          -->
          <span role="status" aria-live="polite" class="mr-4">
            <StatusChip
              v-if="showHealthChip"
              :icon="healthChip.icon"
              :text="healthChip.text"
              :color="healthChip.color"
            />
          </span>

          <UserMenu
            v-if="signedIn"
            :display-name="me!.display"
            @sign-out="handleSignOut"
          />
        </template>

        <!--
          xs/sm: everything above besides the product name and the mode
          indicator collapses into one menu button, instead of shrinking
          or clipping (Fitt's/Hick's law: one large, edge-anchored
          target beats several cramped ones).
        -->
        <AppBarMenu
          v-else
          :show-nav="signedIn || isCallbackRoute"
          :has-config-problem="hasConfigProblem"
          :health="showHealthChip ? healthChip : null"
          :user-display="signedIn ? me!.display : null"
          @sign-out="handleSignOut"
        />
      </v-container>

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
/* Skip-link reveal-on-focus pattern: Vuetify has no utility for an
   off-screen offset that flips to visible on :focus (position, left
   offset and padding move to utility classes above, and `bg-primary`
   -- Vuetify's own generated utility class, which pairs the primary
   background with on-primary text -- replaces the hand-written
   colour pair this rule used to carry; P11-R-10). Only the top-offset
   toggle itself has no Vuetify equivalent. */
.skip-link {
  top: -40px;
  z-index: 100;
}

.skip-link:focus {
  top: 0;
}
</style>

<style>
/* docs/ui-review G-08 (P11-R-04): Vuetify's own focus-visible styling
   does not draw a visible ring for a plain `v-btn` (any variant),
   `v-list-item` (nav links, menu items), a chip's close affordance,
   or a clickable chip -- only a `variant="text"` icon button
   happened to get one from `CopyValueButton.vue`'s now-removed local
   patch. One rule, keyed off the theme's `primary` token, covers all
   four everywhere in the app; unscoped because it has to reach
   markup rendered by other components, not just this file's own
   template (text fields/selects already show a border change on
   focus, and the app uses no tabs component, so neither needs this).
   `.date-tooltip-activator` (SourcesView's relative-date spans, made
   focusable with `tabindex="0"` so keyboard users can reveal the
   absolute date in their `v-tooltip`, P11-R-21) is a plain `<span>`,
   not a Vuetify component, so it needs the same treatment. */
.v-btn:focus-visible,
.v-chip__close:focus-visible,
.v-list-item:focus-visible,
.v-chip--link:focus-visible,
.date-tooltip-activator:focus-visible {
  outline: 2px solid rgb(var(--v-theme-primary));
  outline-offset: 2px;
}
</style>
