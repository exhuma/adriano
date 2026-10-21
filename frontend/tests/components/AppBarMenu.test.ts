/**
 * Ensure the collapsed mobile app-bar menu: lists nav in order, only
 * shows the backend-status row when given one (decision 1: hidden
 * while healthy), merges the shared theme choice alongside sign-out
 * without duplicating controls, and emits `signOut`.
 */
import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";

import vuetify from "@/plugins/vuetify";
import AppBarMenu from "@/components/AppBarMenu.vue";

vi.mock("@/composables/useThemePreference", () => ({
  useThemePreference: () => ({
    preference: { value: "system" },
    setPreference: vi.fn(),
  }),
}));

async function openMenu(props: {
  showNav: boolean;
  hasConfigProblem: boolean;
  health: { icon: string; text: string; color?: string } | null;
  userDisplay: string | null;
}) {
  const wrapper = mount(AppBarMenu, {
    props,
    global: { plugins: [vuetify] },
    attachTo: document.body,
  });
  const activator = document.body.querySelector(
    'button[aria-label="Open menu"]',
  ) as HTMLButtonElement;
  activator.click();
  await flushPromises();
  return wrapper;
}

describe("AppBarMenu", () => {
  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("lists Catalog before Sources when nav is shown", async () => {
    await openMenu({
      showNav: true,
      hasConfigProblem: false,
      health: null,
      userDisplay: null,
    });

    const text = document.body.textContent ?? "";
    expect(text.indexOf("Catalog")).toBeGreaterThanOrEqual(0);
    expect(text.indexOf("Sources")).toBeGreaterThan(text.indexOf("Catalog"));
  });

  it("omits the backend-status row when health is null (healthy)", async () => {
    await openMenu({
      showNav: false,
      hasConfigProblem: false,
      health: null,
      userDisplay: null,
    });

    expect(document.body.textContent).not.toContain("Backend");
  });

  it("shows the backend-status row when given one (degraded/offline)", async () => {
    await openMenu({
      showNav: false,
      hasConfigProblem: false,
      health: {
        icon: "mdi-alert-circle",
        text: "Backend degraded",
        color: "warning",
      },
      userDisplay: null,
    });

    expect(document.body.textContent).toContain("Backend degraded");
  });

  it("merges the theme choice into the signed-in user's section, once", async () => {
    await openMenu({
      showNav: false,
      hasConfigProblem: false,
      health: null,
      userDisplay: "Alice",
    });

    const text = document.body.textContent ?? "";
    expect(text).toContain("Alice");
    expect(text).toContain("Theme");
    expect(text).toContain("Light");
    expect(text).toContain("Dark");
    expect(text).toContain("System");
    expect(text).toContain("Sign out");
    // Exactly one theme switcher -- no duplicate control.
    expect(document.body.querySelectorAll(".v-list-subheader").length).toBe(1);
  });

  it("omits the user section entirely when signed out", async () => {
    await openMenu({
      showNav: false,
      hasConfigProblem: false,
      health: null,
      userDisplay: null,
    });

    expect(document.body.textContent).not.toContain("Theme");
    expect(document.body.textContent).not.toContain("Sign out");
  });

  it("emits signOut when 'Sign out' is clicked", async () => {
    const wrapper = await openMenu({
      showNav: false,
      hasConfigProblem: false,
      health: null,
      userDisplay: "Alice",
    });

    const signOutItem = Array.from(
      document.body.querySelectorAll(".v-list-item"),
    ).find((el) => el.textContent?.includes("Sign out")) as HTMLElement;
    signOutItem.click();
    await flushPromises();

    expect(wrapper.emitted("signOut")).toBeTruthy();
  });
});
