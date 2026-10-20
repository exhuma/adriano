/**
 * Ensure the "says" / "should say" blocks are labelled (not relying
 * on colour alone to distinguish them), and that a missing original
 * text (a pure addition) simply omits that block rather than
 * rendering an empty one.
 */
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import ErratumTextBlocks from "@/components/record/ErratumTextBlocks.vue";

describe("ErratumTextBlocks", () => {
  it("shows the original, corrected, and notes blocks with their labels", () => {
    const wrapper = mount(ErratumTextBlocks, {
      props: {
        originalHtml: "<p>old text</p>",
        correctedHtml: "<p>new text</p>",
        notesHtml: "<p>because reasons</p>",
      },
    });

    expect(wrapper.text()).toContain("Original text — says:");
    expect(wrapper.text()).toContain("old text");
    expect(wrapper.text()).toContain("Corrected text — should say:");
    expect(wrapper.text()).toContain("new text");
    expect(wrapper.text()).toContain("Notes");
    expect(wrapper.text()).toContain("because reasons");
  });

  it("omits the original-text block when there is none (a pure addition)", () => {
    const wrapper = mount(ErratumTextBlocks, {
      props: {
        originalHtml: null,
        correctedHtml: "<p>new text</p>",
        notesHtml: null,
      },
    });

    expect(wrapper.text()).not.toContain("Original text");
    expect(wrapper.text()).not.toContain("Notes");
    expect(wrapper.text()).toContain("Corrected text — should say:");
  });
});
