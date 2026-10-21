/**
 * Ensure the shared theme-choice items render all three options with
 * accessible names, expose the active preference through
 * `role="menuitemradio"` + `aria-checked` (P11-R-14, a radio-group
 * semantics that a plain `aria-current` cannot express), and call
 * `setPreference` with the clicked choice
 * (`phases/11-ui-ux-updates.md` Task 2, decision 6).
 */
import { mount } from "@vue/test-utils";
import { ref } from "vue";
import { describe, expect, it, vi } from "vitest";

import vuetify from "@/plugins/vuetify";
import ThemeMenuItems from "@/components/ThemeMenuItems.vue";
import type { ThemePreference } from "@/composables/useThemePreference";

const preferenceRef = ref<ThemePreference>("system");
const setPreference = vi.fn((value: ThemePreference) => {
  preferenceRef.value = value;
});

vi.mock("@/composables/useThemePreference", () => ({
  useThemePreference: () => ({
    preference: preferenceRef,
    setPreference,
  }),
}));

describe("ThemeMenuItems", () => {
  it("lists Light, Dark, and System, each with an accessible name", () => {
    const wrapper = mount(ThemeMenuItems, { global: { plugins: [vuetify] } });

    expect(wrapper.text()).toContain("Light");
    expect(wrapper.text()).toContain("Dark");
    expect(wrapper.text()).toContain("System");
  });

  it("marks every item as a radio in a labelled group", () => {
    const wrapper = mount(ThemeMenuItems, { global: { plugins: [vuetify] } });

    const group = wrapper.find('[role="group"]');
    const subheader = wrapper.findComponent({ name: "VListSubheader" });
    expect(group.exists()).toBe(true);
    expect(group.attributes("aria-labelledby")).toBe(subheader.attributes("id"));

    const items = wrapper.findAll('[role="menuitemradio"]');
    expect(items).toHaveLength(3);
  });

  it("marks the current preference as checked, the others as not", () => {
    preferenceRef.value = "dark";
    const wrapper = mount(ThemeMenuItems, { global: { plugins: [vuetify] } });

    const items = wrapper.findAll('[role="menuitemradio"]');
    const dark = items.find((item) => item.text().includes("Dark"));
    const light = items.find((item) => item.text().includes("Light"));

    expect(dark?.attributes("aria-checked")).toBe("true");
    expect(light?.attributes("aria-checked")).toBe("false");
  });

  it("calls setPreference with the clicked choice", async () => {
    preferenceRef.value = "system";
    const wrapper = mount(ThemeMenuItems, { global: { plugins: [vuetify] } });
    setPreference.mockClear();

    const items = wrapper.findAll(".v-list-item");
    const lightItem = items.find((item) => item.text().includes("Light"));
    await lightItem!.trigger("click");

    expect(setPreference).toHaveBeenCalledWith("light");
  });
});
