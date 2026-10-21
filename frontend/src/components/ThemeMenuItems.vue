<script setup lang="ts">
/**
 * Light/dark/system theme-choice items for inclusion inside a
 * `v-list` that is itself inside a `v-menu`. Shared between the
 * desktop `UserMenu` and the collapsed mobile `AppBarMenu`
 * so there is one
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
import { useId } from "vue";

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

/** Labels the `role="group"` wrapper below, so the group has an
 *  accessible name without repeating "Theme" in an `aria-label`. */
const subheaderId = useId();
</script>

<template>
  <!--
    P11-R-14: a theme choice is a mutually-exclusive selection, not a
    plain list of actions, so each item is a radio button
    (`role="menuitemradio"` + `aria-checked`) rather than a bare
    `v-list-item` with an `aria-current` that assistive tech has no
    standard way to announce for this role. `menuitemradio`'s
    required ARIA context role is `menu`, `menubar`, or `group`; this
    wrapper -- not the parent `v-menu`'s `v-list` (`role="list"` by
    default, shared with non-theme items in `UserMenu.vue`/
    `AppBarMenu.vue`) -- supplies that `group` context, labelled by
    the existing visible "Theme" subheader instead of a duplicate
    `aria-label`.
  -->
  <div role="group" :aria-labelledby="subheaderId">
    <v-list-subheader :id="subheaderId">Theme</v-list-subheader>
    <v-list-item
      v-for="choice in choices"
      :key="choice.value"
      role="menuitemradio"
      :aria-checked="preference === choice.value"
      :title="choice.title"
      @click="setPreference(choice.value)"
    >
      <template #prepend>
        <v-icon :icon="choice.icon" aria-hidden="true" />
      </template>
      <template v-if="preference === choice.value" #append>
        <v-icon icon="mdi-check" aria-hidden="true" />
      </template>
    </v-list-item>
  </div>
</template>
