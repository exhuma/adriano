/**
 * Ensure the dev-login dialog's role presets come from the catalog
 * (docs/ui-review D-04) and fill the roles field, none are shown while
 * loading or after a failed fetch (manual entry keeps working),
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
const loadDevPresets = vi.fn();

vi.mock("@/auth/devAuth", () => ({
  devSignIn: (...args: unknown[]) => devSignIn(...args),
  loadDevPresets: () => loadDevPresets(),
}));

const PRESETS = [
  { label: "Reader", roles: ["adr-reader"] },
  { label: "Reviewer", roles: ["adr-reader", "adr-reviewer"] },
  { label: "Operator", roles: ["admin"] },
];

function presetLabels(): string[] {
  const group = document.body.querySelector(
    '[role="group"][aria-label="Role presets"]',
  );
  if (!group) {
    return [];
  }
  return Array.from(group.querySelectorAll("button")).map(
    (button) => button.textContent?.trim() ?? "",
  );
}

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
    loadDevPresets.mockReset();
    loadDevPresets.mockResolvedValue(PRESETS);
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

  it("shows the presets derived from the catalog", async () => {
    mountDialog();
    await flushPromises();

    expect(loadDevPresets).toHaveBeenCalledOnce();
    expect(presetLabels()).toEqual(["Reader", "Reviewer", "Operator"]);
  });

  it("shows only the presets the catalog can satisfy", async () => {
    loadDevPresets.mockResolvedValue([PRESETS[0]]);
    mountDialog();
    await flushPromises();

    expect(presetLabels()).toEqual(["Reader"]);
  });

  it("fills the roles field from a preset button", async () => {
    const wrapper = mountDialog();
    await flushPromises();

    buttonByText("Reviewer").click();
    await flushPromises();

    expect((wrapper.vm as unknown as { roles: string }).roles).toBe(
      "adr-reader, adr-reviewer",
    );
  });

  it("shows no presets while the roles are loading", async () => {
    loadDevPresets.mockReturnValue(new Promise(() => {}));
    mountDialog();
    await flushPromises();

    expect(presetLabels()).toEqual([]);
    expect(document.body.textContent).not.toContain("Could not load");
  });

  it("keeps manual entry working when the roles fail to load", async () => {
    loadDevPresets.mockRejectedValue(new ApiError(404, { detail: "x" }));
    devSignIn.mockResolvedValue(undefined);
    const wrapper = mountDialog();
    await flushPromises();

    expect(presetLabels()).toEqual([]);
    expect(document.body.textContent).toContain(
      "Could not load this catalog's roles",
    );
    expect(document.body.querySelector(".v-alert")).toBeNull();

    const vm = wrapper.vm as unknown as { sub: string; roles: string };
    vm.sub = "alice";
    vm.roles = "adr-reader";
    await wrapper.vm.$nextTick();
    buttonByText("Sign in").click();
    await flushPromises();

    expect(devSignIn).toHaveBeenCalledWith(
      expect.objectContaining({ sub: "alice", roles: ["adr-reader"] }),
    );
  });

  it("does not load presets while closed", async () => {
    mountDialog(false);
    await flushPromises();

    expect(loadDevPresets).not.toHaveBeenCalled();
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
