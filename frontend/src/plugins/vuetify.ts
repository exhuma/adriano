/**
 * Vuetify instance and theme (module-vue-vuetify "Vuetify theming").
 *
 * All colours used across the app must be theme tokens referenced by
 * semantic name, never hex/rgb/named CSS colours in components.
 */
// Vuetify's theme names Roboto but does not ship it; without these the
// type scale's medium (500) weights fall back to regular on hosts
// without a local Roboto. Self-hosted latin subset, no external CDN.
import "@fontsource/roboto/latin-400.css";
import "@fontsource/roboto/latin-500.css";
import "@fontsource/roboto/latin-700.css";
import "@mdi/font/css/materialdesignicons.css";
import "vuetify/styles";

import { createVuetify } from "vuetify";
import type { ThemeDefinition } from "vuetify";

/**
 * Status colours double as chip/alert *text* under this app's
 * `variant="tonal"` convention (`StatusChip`, every `v-alert` in
 * `components/record/*`): the colour is the text colour, drawn over
 * a background tinted to Vuetify's `activated-opacity` (12% by
 * default -- see `vuetify/lib/styles/tools/_variant.sass` and
 * `composables/theme.js`'s `genDefaults`). `warning`, `info` and
 * `success` below (light) and `error` (dark) are darkened/lightened
 * from the previous values so the colour, as text, reaches at least
 * 4.5:1 against both the opaque `surface` colour and that 12% tint
 * composited over `surface` -- checked mechanically for every pair,
 * in both themes, by `tests/plugins/vuetify.test.ts` (docs/ui-review
 * G-01). No component currently paints these colours as a solid fill
 * (`variant="flat"/"elevated"`) -- only `variant="tonal"` text/icons
 * and `variant="outlined"` button text/borders -- so no separate
 * bright-fill semantic key is needed per `phases/11-ui-ux-updates.md`
 * Task 1; add one (ladder step 1) if a later task introduces a
 * filled use that needs the brighter hue back.
 */
export const light: ThemeDefinition = {
  dark: false,
  colors: {
    primary: "#1867C0",
    secondary: "#5CBBF6",
    error: "#B00020",
    // Was #FB8C00: 2.1:1 on its own 12% tint (docs/ui-review G-01).
    warning: "#9B5600",
    // Was #0288D1: 3.9:1 as alert text (docs/ui-review G-01).
    info: "#026CA7",
    // Was #2E7D32: 4.4:1 on its own 12% tint at 12px (G-01).
    success: "#2B762F",
    background: "#FFFFFF",
    surface: "#FFFFFF",
  },
};

export const dark: ThemeDefinition = {
  dark: true,
  colors: {
    primary: "#90CAF9",
    secondary: "#81D4FA",
    // Was #CF6679: passes on `surface` (4.63:1) but only 3.99:1 on
    // its own 12% tint -- the one dark-theme colour that did not
    // already clear 4.5:1 everywhere (not called out by the review,
    // which did not check the tonal tint specifically).
    error: "#D67C8D",
    warning: "#FFB74D",
    success: "#81C784",
    info: "#4FC3F7",
    background: "#121212",
    surface: "#1E1E1E",
  },
};

export default createVuetify({
  theme: {
    // Follow the OS by default (docs/ui-review G-06); the
    // `useThemePreference` composable and the user menu (Task 2)
    // override it at runtime via `useTheme().change(...)`, which
    // accepts "system" as well as a theme name.
    defaultTheme: "system",
    themes: { light, dark },
  },
  defaults: {
    VProgressLinear: {
      color: "primary",
    },
    // docs/ui-review G-05: card titles that are real headings
    // (`tag="h2"`/`"h3"`) keep the browser's heading margins, which
    // Vuetify's reset does not zero, adding ~16px above and below
    // inside the card. `class` defaults merge with a call site's own
    // classes, so every card title gets `ma-0` and its spacing comes
    // from the card title's own padding, heading or not.
    VCardTitle: {
      class: "ma-0",
    },
    // docs/ui-review G-07: one card style everywhere -- flat with a
    // low-emphasis border from the theme's default
    // `border-color`/`border-opacity` (12% black in light, 12% white
    // in dark) instead of `variant="outlined"`, whose border is
    // full-opacity `currentColor` regardless of theme.
    VCard: {
      variant: "flat",
      border: true,
    },
    // docs/ui-review G-01 (chip prominence) and G-09: `StatusChip`
    // (the app's only direct `v-chip` user) now gets its look from
    // here instead of hard-coded props, so every call site -- and
    // any future one -- inherits it automatically.
    VChip: {
      variant: "tonal",
      size: "small",
    },
    // docs/ui-review G-09: no empty `role="alert"` message slot when
    // a field has no hint/validation. Fields that set
    // `hint`/`persistent-hint`, or that get a validation error, still
    // show it -- "auto" keeps the details slot whenever there is a
    // message to show.
    VTextField: {
      hideDetails: "auto",
    },
    VSelect: {
      hideDetails: "auto",
    },
    // docs/ui-review G-02/G-03: one page width for every route.
    // Task 2 wires the app bar into the same container (`App.vue`)
    // and dropped `meta.wide`/`.container--wide`.
    VContainer: {
      maxWidth: 1360,
    },
  },
});
