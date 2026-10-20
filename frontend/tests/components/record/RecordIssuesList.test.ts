/**
 * Ensure validation-issue messages wrap in full instead of being cut
 * at one line (docs/ui-review R-09), that the severity is announced
 * to assistive tech, that the card title is a section heading
 * (G-05), and that the static list is not a tab stop (G-10).
 */
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import vuetify from "@/plugins/vuetify";
import RecordIssuesList from "@/components/record/RecordIssuesList.vue";

function mountList() {
  return mount(RecordIssuesList, {
    props: {
      issues: [
        {
          severity: "warning",
          code: "obsolete_kind_field",
          message:
            "`kind` is no longer used: a document is an erratum when " +
            "it has `erratum-for`. Remove `kind: decision`.",
        },
      ],
    },
    global: { plugins: [vuetify] },
  });
}

describe("RecordIssuesList", () => {
  it("lets each message wrap instead of truncating it", () => {
    const wrapper = mountList();

    const title = wrapper.find(".v-list-item-title");
    expect(title.classes()).toEqual(
      expect.arrayContaining(["text-wrap", "text-break"]),
    );
    expect(title.text()).toContain("Remove `kind: decision`.");
  });

  it("announces the severity with a screen-reader-only prefix", () => {
    const wrapper = mountList();

    expect(wrapper.find(".d-sr-only").text()).toBe("warning:");
  });

  it("uses an h2 section heading and no list tab stop", () => {
    const wrapper = mountList();

    expect(wrapper.find("h2").text()).toBe("Validation issues");
    expect(wrapper.find(".v-list").attributes("tabindex")).toBe("-1");
  });
});
