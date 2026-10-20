/**
 * Ensure the provenance card wraps long values instead of cutting
 * them with an ellipsis, offers a copy button for the full file path
 * (docs/ui-review R-09), and is not itself a tab stop (G-10).
 */
import { mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import vuetify from "@/plugins/vuetify";
import RecordProvenanceCard from "@/components/record/RecordProvenanceCard.vue";

const longPath =
  "doc/decisions/2024-09-09-adopt-event-sourcing-for-the-ledger.md";

function mountCard(sourceUrl: string | null = "/srv/repos/payments/x") {
  return mount(RecordProvenanceCard, {
    props: {
      provenance: {
        source_id: "central",
        project: "payments",
        path: longPath,
        ref: "main",
        source_url: sourceUrl,
        updated_at: "2026-02-03T10:00:00Z",
      },
      freshness: {
        last_attempt_at: null,
        last_success_at: null,
        last_status: "never",
        stale: false,
        intake: ["poll"],
      },
    },
    global: { plugins: [vuetify] },
  });
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
    for (const value of [path, location]) {
      expect(value).toBeDefined();
      expect(value!.classes()).toContain("text-break");
      expect(value!.classes()).not.toContain("text-truncate");
    }
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
