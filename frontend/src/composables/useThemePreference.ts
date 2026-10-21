/**
 * Singleton theme-preference state: light/dark/system, persisted in
 * `localStorage` (module-vue-vuetify "State management" -- no
 * Pinia). The product owner's decision treats the stored choice as a
 * convenience only, so every
 * access is wrapped in `try`/`catch`: a blocked, full, or disabled
 * store must never prevent switching themes, it just means the
 * choice is not remembered for next time.
 *
 * Vuetify's own `defaultTheme: "system"` (`plugins/vuetify.ts`)
 * already follows `prefers-color-scheme` for the "system" value, so
 * this composable only has to remember *which* of the three choices
 * is in effect and apply it through `useTheme().change(...)`;
 * the user menu is the only planned caller of `setPreference`.
 *
 * `App.vue`'s own `setup()` calls this composable once, for its
 * apply-on-mount side effect alone (P11-R-01): the previous only
 * caller, `ThemeMenuItems`, lives inside a lazy `v-menu` that never
 * mounts until the user opens it, so a stored non-"system" choice
 * was never applied on page load, signed in or out, until then.
 * Calling the singleton from more than one component is safe and
 * documented above `applied`.
 */
import { readonly, ref } from "vue";
import { useTheme } from "vuetify";

/** The user's theme choice: an explicit theme, or "system" to follow
 *  the OS (`prefers-color-scheme`). */
export type ThemePreference = "light" | "dark" | "system";

const STORAGE_KEY = "adriano:theme-preference";

function isThemePreference(value: unknown): value is ThemePreference {
  return value === "light" || value === "dark" || value === "system";
}

/** Read the stored preference, tolerating a missing, blocked, or
 *  stale value (private browsing, disabled storage, an older
 *  build's value). Defaults to "system". */
function readStoredPreference(): ThemePreference {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    return isThemePreference(stored) ? stored : "system";
  } catch {
    return "system";
  }
}

/** Best-effort persistence; a storage failure must never block the
 *  theme change the user just made. */
function writeStoredPreference(value: ThemePreference): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, value);
  } catch {
    // Ignored: the in-memory preference still applies for the rest
    // of this session (see the module docstring).
  }
}

const preference = ref<ThemePreference>(readStoredPreference());

/** Whether the stored preference has been applied to the live
 *  Vuetify theme yet this session (once per page load is enough;
 *  `useTheme()` returns the same global instance every time). */
let applied = false;

/**
 * Singleton accessor for the current theme preference and a setter
 * that applies it to the live Vuetify theme and persists it.
 *
 * Must be called from inside a component `setup()` (or another
 * composable called from one): it calls Vuetify's `useTheme()`,
 * which looks up the theme instance provided by the `vuetify` plugin.
 *
 * :returns: `preference` (readonly) and `setPreference`.
 */
export function useThemePreference() {
  const theme = useTheme();
  if (!applied) {
    applied = true;
    void theme.change(preference.value);
  }

  /**
   * Switch to `value`, applying it immediately and remembering it
   * for next time (best-effort; see `writeStoredPreference`).
   *
   * :param value: The new preference.
   */
  function setPreference(value: ThemePreference): void {
    preference.value = value;
    void theme.change(value);
    writeStoredPreference(value);
  }

  return {
    preference: readonly(preference),
    setPreference,
  };
}
