<script setup lang="ts">
/**
 * Desktop app-bar user menu: the activator button shows the
 * signed-in display name, and the menu holds the theme choice and
 * sign-out. `v-menu`'s activator slot already applies
 * `aria-haspopup`/`aria-expanded` to the bound button, so none of
 * that is repeated here.
 */
import ThemeMenuItems from "@/components/ThemeMenuItems.vue";

defineProps<{
  /** Signed-in user's display name, shown on the activator and as
   *  the first menu item. */
  displayName: string;
}>();

defineEmits<{
  /** User chose "Sign out" from the menu. */
  signOut: [];
}>();
</script>

<template>
  <v-menu location="bottom end">
    <template #activator="{ props: activatorProps }">
      <v-btn
        v-bind="activatorProps"
        variant="text"
        append-icon="mdi-chevron-down"
      >
        {{ displayName }}
      </v-btn>
    </template>

    <v-list density="comfortable" nav>
      <v-list-item :title="displayName" subtitle="Signed in" />
      <v-divider class="my-1" />

      <ThemeMenuItems />
      <v-divider class="my-1" />

      <v-list-item
        prepend-icon="mdi-logout"
        title="Sign out"
        @click="$emit('signOut')"
      />
    </v-list>
  </v-menu>
</template>
