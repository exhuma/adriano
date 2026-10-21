/**
 * Ensure the provenance card wraps long values instead of cutting
 * them with an ellipsis, offers a copy button for the full file path, and is
 * not itself a tab stop (G-10). The
 * card relies on `RecordSidebar`'s scoped `v-defaults-provider` for
 * the `lines: false` clamp override (P11-R-20), so these tests mount
 * it inside the same scoped defaults, matching production.
 */
import { VDefaultsProvider } from "vuetify/components";
import { defineComponent, h } from "vue";
import { mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import vuetify from "@/plugins/vuetify";
import RecordProvenanceCard from "@/components/record/RecordProvenanceCard.vue";

const longPath =
  "doc/decisions/2024-09-09-adopt-event-sourcing-for-the-ledger.md";

/** Same scoped defaults `RecordSidebar.vue` provides in production. */
const infoCardDefaults = {
  VList: { density: "compact", lines: false },
} as const;

function mountCard(sourceUrl: string | null = "/srv/repos/payments/x") {
  const provenance = {
    source_id: "central",
    project: "payments",
    path: longPath,
    ref: "main",
    source_url: sourceUrl,
    updated_at: "2026-02-03T10:00:00Z",
  };
  const freshness = {
    last_attempt_at: null,
    last_success_at: null,
    last_status: "never" as const,
    stale: false,
    intake: ["poll"] as ("push" | "poll")[],
  };
  const Wrapper = defineComponent({
    render() {
      return h(VDefaultsProvider, { defaults: infoCardDefaults }, () =>
        h(RecordProvenanceCard, { provenance, freshness }),
      );
    },
  });
  return mount(Wrapper, { global: { plugins: [vuetify] } });
}

describe("RecordProvenanceCard", () => {
  beforeEach(() => {
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
      configurable: true,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows the full path and source location as wrapping text", () => {
    const wrapper = mountCard();

    const values = wrapper.findAll(".v-list-item-subtitle");
    const path = values.find((v) => v.text().includes(longPath));
    const location = values.find((v) => v.text().includes("/srv/repos"));
    expect(path).toBeDefined();
    expect(location).toBeDefined();
    // The path sits in a flex row with its copy button (P11-R-20);
    // the wrapping class moves to the inner text span.
    expect(path!.find(".text-break").exists()).toBe(true);
    expect(path!.classes()).not.toContain("text-truncate");
    expect(location!.classes()).toContain("text-break");
    expect(location!.classes()).not.toContain("text-truncate");
  });

  it("keeps the path and its copy button on one row (P11-R-20)", () => {
    const wrapper = mountCard();

    const values = wrapper.findAll(".v-list-item-subtitle");
    const path = values.find((v) => v.text().includes(longPath))!;
    expect(path.classes()).toContain("d-flex");
    expect(path.classes()).toContain("align-start");
    const textSpan = path.find(".text-break");
    expect(textSpan.classes()).toContain("flex-1-1");
  });

  it("never clamps its rows to one line", () => {
    const wrapper = mountCard();

    expect(wrapper.find(".v-list--one-line").exists()).toBe(false);
    expect(wrapper.find(".v-list-item--one-line").exists()).toBe(false);
  });

  it("copies the full file path from a labelled button", async () => {
    const wrapper = mountCard();

    const button = wrapper.find(
      "button[aria-label='Copy file path to clipboard']",
    );
    expect(button.exists()).toBe(true);
    await button.trigger("click");

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(longPath);
    expect(wrapper.text()).toContain("Copied!");
  });

  it("is not a tab stop itself", () => {
    const wrapper = mountCard();

    expect(wrapper.find(".v-list").attributes("tabindex")).toBe("-1");
  });
});
