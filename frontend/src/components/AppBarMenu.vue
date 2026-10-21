<script setup lang="ts">
/**
 * Collapsed app-bar contents for narrow viewports (xs/sm): the
 * primary nav, backend status, configuration-issue warning, the
 * theme choice, and the signed-in user's identity/sign-out action,
 * all reachable from one "Open menu" button instead of overflowing
 * the toolbar (module-ux-principles "Fitt's law & Hick's law": one
 * large, edge-anchored target instead of several cramped ones).
 * Mirrors the desktop app bar's `UserMenu` contents (theme choice +
 * sign-out) so the two never drift into duplicate or conflicting
 * controls.
 *
 * Pure: everything it shows comes from props, and the only side
 * effect it causes is emitting `signOut` for the parent to handle --
 * it owns no auth or health state itself (the theme choice is the
 * one exception, via the shared `useThemePreference` singleton
 * `ThemeMenuItems` calls directly). `v-menu`/`v-overlay` already
 * close on Escape and return focus to the activator button, so no
 * extra focus-management code is needed here.
 */
import ThemeMenuItems from "@/components/ThemeMenuItems.vue";

defineProps<{
  /** Whether the primary nav (Catalog/Sources) should be listed. */
  showNav: boolean;
  /** Whether `/healthz` reports a configuration problem. */
  hasConfigProblem: boolean;
  /** Backend status row to render (icon, label, theme colour), or
   *  `null` to omit it -- the backend is healthy, which is the
   *  default state and carries no information worth a row
   * . */
  health: { icon: string; text: string; color?: string } | null;
  /** Signed-in user's display name, or `null` when signed out. */
  userDisplay: string | null;
}>();

defineEmits<{
  /** The user chose "Sign out" from the menu. */
  signOut: [];
}>();
</script>

<template>
  <v-menu location="bottom end">
    <template #activator="{ props: activatorProps }">
      <v-btn
        v-bind="activatorProps"
        icon="mdi-menu"
        aria-label="Open menu"
        variant="text"
      />
    </template>

    <v-list density="comfortable" nav>
      <template v-if="showNav">
        <v-list-item to="/" title="Catalog" />
        <v-list-item to="/sources" title="Sources" />
        <v-divider class="my-1" />
      </template>

      <v-list-item
        v-if="hasConfigProblem"
        to="/sources"
        aria-label="Configuration issue detected; go to Sources for details"
      >
        <template #prepend>
          <v-icon icon="mdi-cog-outline" color="warning" aria-hidden="true" />
        </template>
        <v-list-item-title>Configuration issue</v-list-item-title>
      </v-list-item>

      <v-list-item v-if="health">
        <template #prepend>
          <v-icon :icon="health.icon" :color="health.color" aria-hidden="true" />
        </template>
        <v-list-item-title>{{ health.text }}</v-list-item-title>
      </v-list-item>

      <template v-if="userDisplay !== null">
        <v-divider class="my-1" />
        <v-list-item :title="userDisplay" subtitle="Signed in" />
        <ThemeMenuItems />
        <v-divider class="my-1" />
        <v-list-item
          prepend-icon="mdi-logout"
          title="Sign out"
          @click="$emit('signOut')"
        />
      </template>
    </v-list>
  </v-menu>
</template>
