/**
 * Ensure the metadata card shows the UUID in short form with the
 * full value reachable via tooltip and copy-to-clipboard
 * (module-ux-principles "Technical identifiers": never show only the
 * shortened form).
 */
import { mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import vuetify from "@/plugins/vuetify";
import RecordMetadataCard from "@/components/record/RecordMetadataCard.vue";

const fullUuid = "22222222-2222-2222-2222-222222222222";

function mountCard() {
  return mount(RecordMetadataCard, {
    props: {
      adrUuid: fullUuid,
      decisionDate: "2024-12-24",
      decisionDateInferred: false,
      recordKind: "decision",
    },
    global: { plugins: [vuetify] },
  });
}

describe("RecordMetadataCard UUID display", () => {
  beforeEach(() => {
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
      configurable: true,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows only the shortened UUID as visible text, with the full value in a tooltip", () => {
    const wrapper = mountCard();

    const code = wrapper.find("code");
    expect(code.text()).toBe("22222222");
    expect(code.text()).not.toBe(fullUuid);
    expect(code.attributes("title")).toBe(fullUuid);
  });

  it("copies the full UUID to the clipboard, not the shortened form", async () => {
    const wrapper = mountCard();

    await wrapper.find("button").trigger("click");

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(fullUuid);
    expect(wrapper.text()).toContain("Copied!");
  });

  it("shows a fallback when there is no valid UUID", () => {
    const wrapper = mount(RecordMetadataCard, {
      props: {
        adrUuid: null,
        decisionDate: null,
        decisionDateInferred: false,
        recordKind: "decision",
      },
      global: { plugins: [vuetify] },
    });

    expect(wrapper.find("code").exists()).toBe(false);
    expect(wrapper.text()).toContain("Not available (no valid UUID in this file)");
  });

  it("labels the date field 'Decision date' for a decision and 'Report date' for an erratum", () => {
    const decisionWrapper = mountCard();
    expect(decisionWrapper.text()).toContain("Decision date");
    expect(decisionWrapper.text()).not.toContain("Report date");

    const erratumWrapper = mount(RecordMetadataCard, {
      props: {
        adrUuid: fullUuid,
        decisionDate: "2025-05-01",
        decisionDateInferred: false,
        recordKind: "erratum",
      },
      global: { plugins: [vuetify] },
    });
    expect(erratumWrapper.text()).toContain("Report date");
    expect(erratumWrapper.text()).not.toContain("Decision date");
  });
});
