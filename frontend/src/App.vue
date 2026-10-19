<script setup lang="ts">
/**
 * Application shell: app bar with navigation and backend status,
 * the mandatory page-loading indicator, and the routed view.
 */
import { computed } from "vue";

import StatusChip from "@/components/StatusChip.vue";
import { useHealth } from "@/composables/useHealth";
import { isLoading } from "@/composables/useLoading";

const { state: healthState } = useHealth();

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
</script>

<template>
  <v-app>
    <a class="skip-link" href="#main-content">Skip to main content</a>

    <v-app-bar :elevation="1">
      <v-app-bar-title>adriano</v-app-bar-title>

      <v-btn to="/" variant="text">Catalog</v-btn>
      <v-btn to="/sources" variant="text">Sources</v-btn>

      <v-spacer />

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
</style>
