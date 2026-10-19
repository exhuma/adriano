<script setup lang="ts">
/**
 * Collapsed app-bar contents for narrow viewports (xs/sm): the
 * primary nav, backend status, configuration-issue warning, and the
 * signed-in user's identity/sign-out action, all reachable from one
 * "Open menu" button instead of overflowing the toolbar
 * (module-ux-principles "Fitt's law & Hick's law": one large,
 * edge-anchored target instead of several cramped ones).
 *
 * Pure: everything it shows comes from props, and the only side
 * effect it causes is emitting `signOut` for the parent to handle --
 * it owns no auth or health state itself. `v-menu`/`v-overlay`
 * already close on Escape and return focus to the activator button,
 * so no extra focus-management code is needed here.
 */
defineProps<{
  /** Whether the primary nav (Catalog/Sources) should be listed. */
  showNav: boolean;
  /** Whether `/healthz` reports a configuration problem. */
  hasConfigProblem: boolean;
  /** Backend status row to render (icon, label, theme colour). */
  health: { icon: string; text: string; color?: string };
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

      <v-list-item>
        <template #prepend>
          <v-icon :icon="health.icon" :color="health.color" aria-hidden="true" />
        </template>
        <v-list-item-title>{{ health.text }}</v-list-item-title>
      </v-list-item>

      <template v-if="userDisplay !== null">
        <v-divider class="my-1" />
        <v-list-item :title="userDisplay" subtitle="Signed in" />
        <v-list-item
          prepend-icon="mdi-logout"
          title="Sign out"
          @click="$emit('signOut')"
        />
      </template>
    </v-list>
  </v-menu>
</template>
