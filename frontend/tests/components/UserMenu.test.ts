/**
 * Ensure the desktop user menu shows the display name on its
 * activator, holds the theme choice and sign-out inside the menu,
 * and emits `signOut` (`phases/11-ui-ux-updates.md` Task 2).
 */
import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";

import vuetify from "@/plugins/vuetify";
import UserMenu from "@/components/UserMenu.vue";

const setPreference = vi.fn();

vi.mock("@/composables/useThemePreference", () => ({
  useThemePreference: () => ({
    preference: { value: "system" },
    setPreference,
  }),
}));

describe("UserMenu", () => {
  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("shows the display name on the activator button", () => {
    const wrapper = mount(UserMenu, {
      props: { displayName: "Alice" },
      global: { plugins: [vuetify] },
    });

    expect(wrapper.text()).toContain("Alice");
  });

  it("opens to reveal the theme choice and sign-out", async () => {
    mount(UserMenu, {
      props: { displayName: "Alice" },
      global: { plugins: [vuetify] },
      attachTo: document.body,
    });

    const activator = document.body.querySelector(
      "button",
    ) as HTMLButtonElement;
    activator.click();
    await flushPromises();

    expect(document.body.textContent).toContain("Theme");
    expect(document.body.textContent).toContain("Light");
    expect(document.body.textContent).toContain("Dark");
    expect(document.body.textContent).toContain("System");
    expect(document.body.textContent).toContain("Sign out");
  });

  it("emits signOut when 'Sign out' is clicked", async () => {
    const wrapper = mount(UserMenu, {
      props: { displayName: "Alice" },
      global: { plugins: [vuetify] },
      attachTo: document.body,
    });

    const activator = document.body.querySelector(
      "button",
    ) as HTMLButtonElement;
    activator.click();
    await flushPromises();

    const signOutItem = Array.from(
      document.body.querySelectorAll(".v-list-item"),
    ).find((el) => el.textContent?.includes("Sign out")) as HTMLElement;
    signOutItem.click();
    await flushPromises();

    expect(wrapper.emitted("signOut")).toBeTruthy();
  });
});
