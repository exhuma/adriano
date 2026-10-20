<script setup lang="ts">
/**
 * Light/dark/system theme-choice items for inclusion inside a
 * `v-list` that is itself inside a `v-menu`. Shared between the
 * desktop `UserMenu` and the collapsed mobile `AppBarMenu`
 * (`phases/11-ui-ux-updates.md` Task 2, decision 6) so there is one
 * implementation of the theme switcher rather than two copies
 * drifting apart.
 *
 * Calls `useThemePreference()` itself instead of taking the
 * preference as a prop: the composable is a documented singleton
 * safe to call from more than one component
 * (`composables/useThemePreference.ts`), which avoids drilling the
 * current preference and setter through both parent menus
 * (`module-vue-vuetify` "component design": composables over prop
 * drilling past one level).
 */
import { useThemePreference } from "@/composables/useThemePreference";
import type { ThemePreference } from "@/composables/useThemePreference";

const { preference, setPreference } = useThemePreference();

/** The three choices offered, in display order. */
const choices: Array<{
  value: ThemePreference;
  title: string;
  icon: string;
}> = [
  { value: "light", title: "Light", icon: "mdi-white-balance-sunny" },
  { value: "dark", title: "Dark", icon: "mdi-weather-night" },
  { value: "system", title: "System", icon: "mdi-theme-light-dark" },
];
</script>

<template>
  <v-list-subheader>Theme</v-list-subheader>
  <v-list-item
    v-for="choice in choices"
    :key="choice.value"
    :title="choice.title"
    :aria-current="preference === choice.value ? 'true' : undefined"
    @click="setPreference(choice.value)"
  >
    <template #prepend>
      <v-icon :icon="choice.icon" aria-hidden="true" />
    </template>
    <template v-if="preference === choice.value" #append>
      <v-icon icon="mdi-check" aria-hidden="true" />
    </template>
  </v-list-item>
</template>
