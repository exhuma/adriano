/**
 * Ensure the dev-login dialog's role presets come from the catalog
 * and fill the roles field, none are shown while
 * loading or after a failed fetch (manual entry keeps working),
 * Cancel closes without signing in, a successful/failed submission
 * is handled (`module-dev-auth-bypass`, module-ux-principles "UI
 * modes": Cancel never mutates state), and the dialog has an
 * accessible name.
 *
 * `v-dialog` teleports its content to `document.body` (outside the
 * mounted wrapper's own DOM subtree), so interactive elements inside
 * it are found and clicked via `document.body`, not
 * `wrapper.findAll`/`trigger`.
 */
import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { VDialog } from "vuetify/components";

import vuetify from "@/plugins/vuetify";
import DevLoginDialog from "@/components/DevLoginDialog.vue";
import { ApiError } from "@/api";

/** jsdom has no `IntersectionObserver`, and Vuetify decides at import
 *  time whether `v-intersect` (behind the `autofocus` prop) is active,
 *  so a fake is installed before any import. Its callbacks are fired
 *  on demand to simulate an intersection change. */
const intersection = vi.hoisted(() => {
  const instances: {
    callback: IntersectionObserverCallback;
    targets: Element[];
  }[] = [];
  class FakeObserver {
    readonly targets: Element[] = [];
    constructor(readonly callback: IntersectionObserverCallback) {
      instances.push(this);
    }
    observe(target: Element): void {
      this.targets.push(target);
    }
    unobserve(): void {}
    disconnect(): void {}
    takeRecords(): IntersectionObserverEntry[] {
      return [];
    }
  }
  Object.assign(globalThis, { IntersectionObserver: FakeObserver });
  return {
    fireAll(): void {
      for (const { callback, targets } of instances) {
        const entries = targets.map(
          (target) =>
            ({ target, isIntersecting: true }) as IntersectionObserverEntry,
        );
        if (entries.length) {
          callback(entries, {} as IntersectionObserver);
        }
      }
    },
  };
});

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

function inputByLabel(label: string): HTMLInputElement {
  const labelEl = Array.from(document.querySelectorAll("label[for]")).find(
    (candidate) => candidate.textContent?.trim() === label,
  ) as HTMLLabelElement | undefined;
  const input = labelEl?.htmlFor
    ? (document.getElementById(labelEl.htmlFor) as HTMLInputElement | null)
    : null;
  if (!input) {
    throw new Error(`No input labelled "${label}" found`);
  }
  return input;
}

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
    vi.useRealTimers();
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

  it("never autofocuses Subject by intersection", () => {
    mountDialog();

    const subject = inputByLabel("Subject (sub)");
    expect(subject.hasAttribute("autofocus")).toBe(false);
  });

  it("focuses Subject once the open transition ends", async () => {
    const wrapper = mountDialog();
    await flushPromises();

    wrapper.findComponent(VDialog).vm.$emit("afterEnter");
    await flushPromises();

    expect(document.activeElement).toBe(inputByLabel("Subject (sub)"));
  });

  it("keeps focus and typed values when presets arrive late", async () => {
    // Vuetify's `autofocus` re-fires on every intersection change (the
    // dialog grows when presets appear); simulate that change by
    // firing every observer once the presets have rendered.
    vi.useFakeTimers();
    let resolvePresets: (value: typeof PRESETS) => void = () => {};
    loadDevPresets.mockReturnValue(
      new Promise((resolve) => {
        resolvePresets = resolve;
      }),
    );
    const wrapper = mountDialog();
    wrapper.findComponent(VDialog).vm.$emit("afterEnter");
    await flushPromises();
    const vm = wrapper.vm as unknown as { sub: string; roles: string };
    vm.sub = "operator";
    const rolesInput = inputByLabel("Roles (comma-separated)");
    rolesInput.focus();
    vm.roles = "admin";
    await wrapper.vm.$nextTick();

    resolvePresets(PRESETS);
    await flushPromises();
    intersection.fireAll();
    vi.advanceTimersByTime(500);
    await flushPromises();
    vi.useRealTimers();

    expect(presetLabels()).toEqual(["Reader", "Reviewer", "Operator"]);
    expect(document.activeElement).toBe(rolesInput);
    expect(vm.sub).toBe("operator");
    expect(vm.roles).toBe("admin");
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
