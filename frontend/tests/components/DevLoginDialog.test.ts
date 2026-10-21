/**
 * Ensure the dev-login dialog's role presets fill the roles field,
 * Cancel closes without signing in, a successful/failed submission
 * is handled (`module-dev-auth-bypass`, module-ux-principles "UI
 * modes": Cancel never mutates state), and the dialog has an
 * accessible name (docs/ui-review D-01).
 *
 * `v-dialog` teleports its content to `document.body` (outside the
 * mounted wrapper's own DOM subtree), so interactive elements inside
 * it are found and clicked via `document.body`, not
 * `wrapper.findAll`/`trigger`.
 */
import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import vuetify from "@/plugins/vuetify";
import DevLoginDialog from "@/components/DevLoginDialog.vue";
import { ApiError } from "@/api";

const devSignIn = vi.fn();

vi.mock("@/auth/devAuth", () => ({
  devSignIn: (...args: unknown[]) => devSignIn(...args),
}));

function mountDialog(modelValue = true) {
  return mount(DevLoginDialog, {
    props: { modelValue },
    global: { plugins: [vuetify] },
    attachTo: document.body,
  });
}

function buttonByText(text: string): HTMLButtonElement {
  const button = Array.from(document.querySelectorAll("button")).find(
    (candidate) => candidate.textContent?.trim() === text,
  );
  if (!button) {
    throw new Error(`No button with text "${text}" found in document.body`);
  }
  return button;
}

describe("DevLoginDialog", () => {
  beforeEach(() => {
    devSignIn.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    document.body.innerHTML = "";
  });

  it("has an accessible name naming the dialog", () => {
    mountDialog();

    const dialog = document.body.querySelector('[role="dialog"]')!;
    const labelledBy = dialog.getAttribute("aria-labelledby")!;
    expect(labelledBy).toBeTruthy();
    const heading = document.getElementById(labelledBy)!;
    expect(heading.tagName).toBe("H2");
    expect(heading.textContent?.trim()).toBe("Dev sign-in");
    expect(heading.className).toContain("text-title-large");
  });

  it("fills the roles field from a preset button", async () => {
    const wrapper = mountDialog();

    buttonByText("Operator/Admin").click();
    await flushPromises();

    expect((wrapper.vm as unknown as { roles: string }).roles).toBe("admin");
  });

  it("Cancel closes the dialog without signing in", async () => {
    const wrapper = mountDialog();

    buttonByText("Cancel").click();
    await flushPromises();

    expect(wrapper.emitted("update:modelValue")).toEqual([[false]]);
    expect(devSignIn).not.toHaveBeenCalled();
  });

  it("submits the entered identity and emits signed-in on success", async () => {
    devSignIn.mockResolvedValue(undefined);
    const wrapper = mountDialog();
    const vm = wrapper.vm as unknown as {
      sub: string;
      roles: string;
    };
    vm.sub = "alice";
    vm.roles = "reader, admin";
    await wrapper.vm.$nextTick();

    buttonByText("Sign in").click();
    await flushPromises();

    expect(devSignIn).toHaveBeenCalledWith({
      sub: "alice",
      name: undefined,
      email: undefined,
      roles: ["reader", "admin"],
    });
    expect(wrapper.emitted("signed-in")).toBeTruthy();
    expect(wrapper.emitted("update:modelValue")).toContainEqual([false]);
  });

  it("shows an actionable message when dev auth is unconfigured (503)", async () => {
    devSignIn.mockRejectedValue(new ApiError(503, { detail: "nope", code: "auth_unconfigured" }));
    const wrapper = mountDialog();
    const vm = wrapper.vm as unknown as { sub: string };
    vm.sub = "alice";
    await wrapper.vm.$nextTick();

    buttonByText("Sign in").click();
    await flushPromises();

    expect(document.body.textContent).toContain("ADRIANO_DEV_SHARED_SECRET");
    expect(wrapper.emitted("signed-in")).toBeFalsy();
  });
});
