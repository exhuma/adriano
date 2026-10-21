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
 * in both themes, by `tests/plugins/vuetify.test.ts`. No component currently
 * paints these colours as a solid fill
 * (`variant="flat"/"elevated"`) -- only `variant="tonal"` text/icons
 * and `variant="outlined"` button text/borders -- so no separate
 * bright-fill semantic key is needed per the Vuetify-first ladder
 * Task 1; add one (ladder step 1) if a later task introduces a
 * filled use that needs the brighter hue back.
 */
export const light: ThemeDefinition = {
  dark: false,
  colors: {
    primary: "#1867C0",
    secondary: "#5CBBF6",
    error: "#B00020",
    // Was #FB8C00: 2.1:1 on its own 12% tint.
    warning: "#9B5600",
    // Was #0288D1: 3.9:1 as alert text.
    info: "#026CA7",
    // Was #2E7D32: 4.4:1 on its own 12% tint at 12px (G-01).
    success: "#2B762F",
    background: "#FFFFFF",
    surface: "#FFFFFF",
  },
  variables: {
    // P11-R-03: Vuetify's default `medium-emphasis-opacity` (0.60)
    // is a plain CSS `opacity` on the whole element -- not a colour
    // mix -- for `.v-label` (field labels), `.v-list-item-subtitle`
    // (sidebar list values), and anything nested inside either (a
    // `StatusChip` nested in a subtitle, e.g. the "Inferred from
    // filename" chip in `RecordMetadataCard.vue`, is blended toward
    // the background as one group with its text). The independent
    // review measured that pairing at 4.30:1 on the opaque surface
    // and 4.39:1 over the list item's 4% hover overlay -- both below
    // 4.5:1. 0.66 clears 4.5:1 with margin in both cases
    // (`tests/plugins/vuetify.test.ts`); only light needs raising --
    // dark's default (0.70) already passes.
    "medium-emphasis-opacity": 0.66,
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
    // Follow the OS by default; the
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
    // card titles that are real headings
    // (`tag="h2"`/`"h3"`) keep the browser's heading margins, which
    // Vuetify's reset does not zero, adding ~16px above and below
    // inside the card. `class` defaults merge with a call site's own
    // classes, so every card title gets `ma-0` and its spacing comes
    // from the card title's own padding, heading or not.
    VCardTitle: {
      class: "ma-0",
    },
    // one card style everywhere -- flat with a
    // low-emphasis border from the theme's default
    // `border-color`/`border-opacity` (12% black in light, 12% white
    // in dark) instead of `variant="outlined"`, whose border is
    // full-opacity `currentColor` regardless of theme.
    VCard: {
      variant: "flat",
      border: true,
    },
    // Chip prominence: `StatusChip`
    // (the app's only direct `v-chip` user) now gets its look from
    // here instead of hard-coded props, so every call site -- and
    // any future one -- inherits it automatically.
    VChip: {
      variant: "tonal",
      size: "small",
    },
    // no empty `role="alert"` message slot when
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
    // one page width for every route.
    // Task 2 wires the app bar into the same container (`App.vue`)
    // and dropped `meta.wide`/`.container--wide`.
    VContainer: {
      maxWidth: 1360,
    },
    // P11-R-06/R-18: `VDialog` wraps its default slot in its own
    // `<VDefaultsProvider root="VDialog">` (`VDialog.js`), which
    // resets to the root defaults tree and merges this nested object
    // on top -- so every `VCardTitle`/`VCardSubtitle`/`VCardText`
    // rendered inside *any* `v-dialog` picks this up, without each
    // dialog repeating its own `v-defaults-provider`
    // (`DecisionDialog.vue`, `DevLoginDialog.vue` used to). `ma-0` is
    // restated here (not merged from the global `VCardTitle` default
    // above) because this is a separate nested-defaults bucket, not
    // an extension of it. `px-6` on all three aligns the title,
    // subtitle, and body at the same 24px horizontal inset (the
    // Dev sign-in subtitle included); `text-wrap` stops a long
    // decision title from being clipped at the dialog's `max-width`.
    VDialog: {
      VCardTitle: { class: "ma-0 px-6 text-wrap" },
      VCardSubtitle: { class: "px-6" },
      VCardText: { class: "px-6" },
    },
  },
});
