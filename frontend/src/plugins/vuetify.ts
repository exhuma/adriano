/**
 * Vuetify instance and theme (module-vue-vuetify "Vuetify theming").
 *
 * All colours used across the app must be theme tokens referenced by
 * semantic name, never hex/rgb/named CSS colours in components.
 */
import "@mdi/font/css/materialdesignicons.css";
import "vuetify/styles";

import { createVuetify } from "vuetify";

export default createVuetify({
  theme: {
    defaultTheme: "light",
    themes: {
      light: {
        dark: false,
        colors: {
          primary: "#1867C0",
          secondary: "#5CBBF6",
          error: "#B00020",
          warning: "#FB8C00",
          success: "#2E7D32",
          info: "#0288D1",
          background: "#FFFFFF",
          surface: "#FFFFFF",
        },
      },
      dark: {
        dark: true,
        colors: {
          primary: "#90CAF9",
          secondary: "#81D4FA",
          error: "#CF6679",
          warning: "#FFB74D",
          success: "#81C784",
          info: "#4FC3F7",
          background: "#121212",
          surface: "#1E1E1E",
        },
      },
    },
  },
  defaults: {
    VProgressLinear: {
      color: "primary",
    },
  },
});
