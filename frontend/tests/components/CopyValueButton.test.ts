/**
 * Ensure `CopyValueButton`'s "Copied!" confirmation is announced to
 * assistive tech through a polite live region (P11-R-21), not only
 * shown visually, and that its hide timer is cleared on unmount so a
 * stale timeout never touches refs of a gone component.
 */
import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import vuetify from "@/plugins/vuetify";
import CopyValueButton from "@/components/CopyValueButton.vue";

function mountButton(value = "sha256-v1:abcdef", label = "digest") {
  return mount(CopyValueButton, {
    props: { value, label },
    global: { plugins: [vuetify] },
  });
}

describe("CopyValueButton", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
      configurable: true,
    });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("has an empty live region before any copy", () => {
    const wrapper = mountButton();

    const live = wrapper.find("[aria-live='polite']");
    expect(live.exists()).toBe(true);
    expect(live.text()).toBe("");
  });

  it("announces the copy through the live region, not only visually", async () => {
    const wrapper = mountButton("sha256-v1:abcdef", "digest");

    await wrapper.find("button").trigger("click");
    await flushPromises();

    expect(wrapper.text()).toContain("Copied!");
    const live = wrapper.find("[aria-live='polite']");
    expect(live.text()).toBe("digest copied to clipboard.");
    // The visible "Copied!" text is decorative; the live region alone
    // carries the announcement, so it must not double up.
    const visible = wrapper.findAll("span").find((s) => s.text() === "Copied!");
    expect(visible?.attributes("aria-hidden")).toBe("true");
  });

  it("clears the live region and visible text after the timeout", async () => {
    const wrapper = mountButton();

    await wrapper.find("button").trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("Copied!");

    await vi.advanceTimersByTimeAsync(2000);

    expect(wrapper.text()).not.toContain("Copied!");
    expect(wrapper.find("[aria-live='polite']").text()).toBe("");
  });

  it("re-announces a second copy of the same value", async () => {
    const wrapper = mountButton();

    await wrapper.find("button").trigger("click");
    await flushPromises();
    await vi.advanceTimersByTimeAsync(2000);
    expect(wrapper.find("[aria-live='polite']").text()).toBe("");

    await wrapper.find("button").trigger("click");
    await flushPromises();

    expect(wrapper.find("[aria-live='polite']").text()).toBe(
      "digest copied to clipboard.",
    );
  });

  it("clears the pending hide timer on unmount instead of leaking it", async () => {
    const wrapper = mountButton();
    const clearSpy = vi.spyOn(global, "clearTimeout");

    await wrapper.find("button").trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("Copied!");

    wrapper.unmount();

    expect(clearSpy).toHaveBeenCalled();
    // Advancing time after unmount must not throw or touch any ref
    // of the now-destroyed component.
    await expect(
      vi.advanceTimersByTimeAsync(5000),
    ).resolves.not.toThrow();
  });

  it("tolerates a clipboard write failure without crashing", async () => {
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText: vi.fn().mockRejectedValue(new Error("denied")) },
      configurable: true,
    });
    const wrapper = mountButton();

    await wrapper.find("button").trigger("click");
    await flushPromises();

    expect(wrapper.text()).not.toContain("Copied!");
    expect(wrapper.find("[aria-live='polite']").text()).toBe("");
  });
});
