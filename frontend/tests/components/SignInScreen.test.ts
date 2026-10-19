/**
 * Ensure the signed-out screen offers only the sign-in methods that
 * are actually available, and never renders the dev-login entry
 * point when the dev-auth gate is off.
 */
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import vuetify from "@/plugins/vuetify";
import SignInScreen from "@/components/SignInScreen.vue";

describe("SignInScreen", () => {
  it("shows no dev-login entry point when the dev-auth gate is off", () => {
    const wrapper = mount(SignInScreen, {
      props: { oidcAvailable: true, devAuthAvailable: false },
      global: { plugins: [vuetify] },
    });

    expect(wrapper.text()).not.toContain("Dev sign-in");
    expect(wrapper.text()).toContain("Sign in");
  });

  it("offers dev sign-in only when the gate is on", async () => {
    const wrapper = mount(SignInScreen, {
      props: { oidcAvailable: false, devAuthAvailable: true },
      global: { plugins: [vuetify] },
    });

    expect(wrapper.text()).toContain("Dev sign-in");
    const devButton = wrapper
      .findAll("button")
      .find((btn) => btn.text() === "Dev sign-in");
    expect(devButton).toBeDefined();
    await devButton!.trigger("click");
    expect(wrapper.emitted("open-dev-login")).toBeTruthy();
  });

  it("explains when no sign-in method is available at all", () => {
    const wrapper = mount(SignInScreen, {
      props: { oidcAvailable: false, devAuthAvailable: false },
      global: { plugins: [vuetify] },
    });

    expect(wrapper.text()).toContain("No sign-in method is available");
  });
});
