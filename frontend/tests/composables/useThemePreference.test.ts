/**
 * Ensure `useThemePreference` defaults to "system" with nothing
 * stored, remembers and re-applies an explicit choice across
 * reloads, actually drives the live Vuetify theme (not just its own
 * state), and keeps working -- in memory, for the rest of the
 * session -- when `localStorage` throws on read or on write
 * (private browsing, disabled storage, quota; DECISIONS.md "Phase 11
 * updates": the stored choice is a convenience, never a
 * requirement).
 */
import { mount, type VueWrapper } from "@vue/test-utils";
import { defineComponent, h } from "vue";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import vuetify from "@/plugins/vuetify";
import type { useThemePreference as UseThemePreference } from
  "@/composables/useThemePreference";

const STORAGE_KEY = "adriano:theme-preference";

type ThemePreferenceApi = ReturnType<typeof UseThemePreference>;

/**
 * Mount a probe component that calls the (freshly re-imported --
 * see `vi.resetModules()` below) singleton composable, so
 * `useTheme()` can find the Vuetify theme instance the real plugin
 * provides. Returns the wrapper plus the composable's own return
 * value, captured by closure rather than read back off the
 * component instance (`defineComponent` with a plain `render()`
 * option, as used here, does not expose `setup()`'s return value on
 * `VueWrapper.vm`'s type).
 */
async function mountProbe(): Promise<{
  wrapper: VueWrapper;
  api: ThemePreferenceApi;
}> {
  const { useThemePreference } = await import(
    "@/composables/useThemePreference"
  );
  let api!: ThemePreferenceApi;
  const Probe = defineComponent({
    setup() {
      api = useThemePreference();
      return () => h("span");
    },
  });
  const wrapper = mount(Probe, { global: { plugins: [vuetify] } });
  return { wrapper, api };
}

describe("useThemePreference", () => {
  let wrapper: VueWrapper | null = null;

  beforeEach(() => {
    vi.resetModules();
    window.localStorage.clear();
  });

  afterEach(() => {
    wrapper?.unmount();
    wrapper = null;
    vi.restoreAllMocks();
    window.localStorage.clear();
  });

  it("defaults to \"system\" when nothing is stored", async () => {
    const mounted = await mountProbe();
    wrapper = mounted.wrapper;

    expect(mounted.api.preference.value).toBe("system");
  });

  it("reads a previously stored preference", async () => {
    window.localStorage.setItem(STORAGE_KEY, "dark");

    const mounted = await mountProbe();
    wrapper = mounted.wrapper;

    expect(mounted.api.preference.value).toBe("dark");
  });

  it("falls back to \"system\" for a value it does not recognise", async () => {
    // e.g. a stale value from a build that offered more choices.
    window.localStorage.setItem(STORAGE_KEY, "sepia");

    const mounted = await mountProbe();
    wrapper = mounted.wrapper;

    expect(mounted.api.preference.value).toBe("system");
  });

  it("applies the stored/default preference on mount", async () => {
    window.localStorage.setItem(STORAGE_KEY, "dark");

    const mounted = await mountProbe();
    wrapper = mounted.wrapper;

    expect(vuetify.theme.name.value).toBe("dark");
  });

  it("switches the live theme and its own state when asked", async () => {
    const mounted = await mountProbe();
    wrapper = mounted.wrapper;

    mounted.api.setPreference("light");

    expect(mounted.api.preference.value).toBe("light");
    expect(vuetify.theme.name.value).toBe("light");
  });

  it("persists a new preference for next time", async () => {
    const mounted = await mountProbe();
    wrapper = mounted.wrapper;

    mounted.api.setPreference("dark");

    expect(window.localStorage.getItem(STORAGE_KEY)).toBe("dark");
  });

  it("falls back to \"system\" when reading storage throws", async () => {
    vi.spyOn(window.localStorage, "getItem").mockImplementation(() => {
      throw new Error("storage is blocked");
    });

    const mounted = await mountProbe();
    wrapper = mounted.wrapper;

    expect(mounted.api.preference.value).toBe("system");
  });

  it("still switches the theme when storage throws on write", async () => {
    vi.spyOn(window.localStorage, "setItem").mockImplementation(() => {
      throw new Error("quota exceeded");
    });

    const mounted = await mountProbe();
    wrapper = mounted.wrapper;

    expect(() => mounted.api.setPreference("dark")).not.toThrow();
    expect(mounted.api.preference.value).toBe("dark");
    expect(vuetify.theme.name.value).toBe("dark");
  });
});
