/**
 * Ensure `RecordHeader` shows the right accepted-candidate note for
 * each record kind (a decision's "authoritative before publication"
 * note never appears for an erratum, which gets its own accurate
 * wording instead), and renders an optional subtitle line under the
 * `h1`.
 */
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import vuetify from "@/plugins/vuetify";
import RecordHeader from "@/components/record/RecordHeader.vue";

function mountHeader(overrides: Partial<Record<string, unknown>> = {}) {
  return mount(RecordHeader, {
    props: {
      title: "Use PostgreSQL",
      subtitle: null,
      recordKind: "decision",
      recordKindLabel: null,
      recordTypeLabel: null,
      issueIndicator: null,
      provenanceSentence: "",
      showAcceptedCandidateNote: false,
      ...overrides,
    },
    global: { plugins: [vuetify] },
  });
}

describe("RecordHeader", () => {
  it("shows the decision 'authoritative before publication' note for an accepted decision candidate", () => {
    const wrapper = mountHeader({
      recordKind: "decision",
      showAcceptedCandidateNote: true,
    });

    expect(wrapper.text()).toContain(
      "Accepted — this candidate is authoritative for implementation " +
        "before publication.",
    );
  });

  it("never shows the decision note for an erratum, showing accurate erratum wording instead", () => {
    const wrapper = mountHeader({
      recordKind: "erratum",
      showAcceptedCandidateNote: true,
    });

    expect(wrapper.text()).not.toContain("authoritative for implementation");
    expect(wrapper.text()).toContain(
      "Verified — this correction applies once published.",
    );
  });

  it("shows no note at all when the candidate was not accepted", () => {
    const wrapper = mountHeader({
      recordKind: "erratum",
      showAcceptedCandidateNote: false,
    });

    expect(wrapper.text()).not.toContain("Verified");
    expect(wrapper.text()).not.toContain("authoritative");
  });

  it("renders an optional subtitle line under the h1", () => {
    const wrapper = mountHeader({ subtitle: "Section: Consequences" });

    expect(wrapper.find("h1").text()).toBe("Use PostgreSQL");
    expect(wrapper.text()).toContain("Section: Consequences");
  });
});
