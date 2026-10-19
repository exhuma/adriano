<script setup lang="ts">
/**
 * Application shell: app bar with navigation and backend status,
 * the mandatory page-loading indicator, and the routed view.
 */
import { computed } from "vue";

import StatusChip from "@/components/StatusChip.vue";
import { useHealth } from "@/composables/useHealth";
import { isLoading } from "@/composables/useLoading";

const { state: healthState, payload: healthPayload } = useHealth();

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

/** Whether `/healthz` reports a problem with `catalog.yaml` or the
 *  approval policy, surfaced as a warning linking to Sources rather
 *  than left for operators to discover only on the sources page. */
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
</script>

<template>
  <v-app>
    <a class="skip-link" href="#main-content">Skip to main content</a>

    <v-app-bar :elevation="1">
      <v-app-bar-title>adriano</v-app-bar-title>

      <v-btn to="/" variant="text">Catalog</v-btn>
      <v-btn to="/sources" variant="text">Sources</v-btn>

      <v-spacer />

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
        <router-view />
      </v-container>
    </v-main>
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
