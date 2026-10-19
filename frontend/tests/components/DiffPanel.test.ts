/**
 * Ensure DiffPanel renders the header (source/project/ref and last
 * indexed time, plus both digest labels), the no-prior-revision and
 * identical-revisions cases, and a normal diff with classified
 * +/- lines and the added/removed summary.
 */
import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";

import vuetify from "@/plugins/vuetify";
import DiffPanel from "@/components/DiffPanel.vue";
import type { RecordDiffOut } from "@/types/approval";

const getRecordDiff = vi.fn();

vi.mock("@/api/records", () => ({
  getRecordDiff: (...args: unknown[]) => getRecordDiff(...args),
}));

const baseProps = {
  recordId: "11111111-1111-1111-1111-111111111111",
  currentDigest: "sha256-v1:current",
  previousDigest: null,
  sourceId: "central",
  project: "platform",
  refName: "main",
  lastIndexedAt: "2026-01-01T00:00:00Z",
  history: [],
  siblings: [],
  competingCandidates: [],
};

function mountPanel(diff: RecordDiffOut) {
  getRecordDiff.mockResolvedValue(diff);
  return mount(DiffPanel, {
    props: baseProps,
    global: { plugins: [vuetify] },
  });
}

describe("DiffPanel", () => {
  it("shows the source/project/ref and last-indexed header", async () => {
    const wrapper = mountPanel({
      base: null,
      target: { digest: "sha256-v1:current", label: "current revision", decided_at: null },
      reason: "no_prior_revision",
      unified_diff: "",
      identical: false,
      lines_added: 0,
      lines_removed: 0,
    });
    await flushPromises();

    expect(wrapper.text()).toContain("central / platform @ main");
    expect(wrapper.text()).toContain("last indexed");
  });

  it("shows 'no prior revision' when there is nothing to compare", async () => {
    const wrapper = mountPanel({
      base: null,
      target: { digest: "sha256-v1:current", label: "current revision", decided_at: null },
      reason: "no_prior_revision",
      unified_diff: "",
      identical: false,
      lines_added: 0,
      lines_removed: 0,
    });
    await flushPromises();

    expect(wrapper.text()).toContain("No prior revision exists to compare against.");
  });

  it("shows the 'identical' message when base and target match", async () => {
    const wrapper = mountPanel({
      base: { digest: "sha256-v1:aaa", label: "accepted", decided_at: "2026-01-01T00:00:00Z" },
      target: { digest: "sha256-v1:current", label: "current revision", decided_at: null },
      reason: null,
      unified_diff: "",
      identical: true,
      lines_added: 0,
      lines_removed: 0,
    });
    await flushPromises();

    expect(wrapper.text()).toContain("These two revisions are identical.");
  });

  it("renders a normal diff with classified +/- lines, header labels, and the summary", async () => {
    const wrapper = mountPanel({
      base: { digest: "sha256-v1:aaa", label: "accepted", decided_at: "2026-01-01T00:00:00Z" },
      target: { digest: "sha256-v1:current", label: "current revision", decided_at: null },
      reason: null,
      unified_diff:
        "--- a\n+++ b\n@@ -1,2 +1,2 @@\n-old line\n+new line\n context line\n",
      identical: false,
      lines_added: 1,
      lines_removed: 1,
    });
    await flushPromises();

    expect(wrapper.text()).toContain("accepted");
    expect(wrapper.text()).toContain("current revision");
    expect(wrapper.text()).toContain("1 line added, 1 line removed");
    expect(wrapper.find(".diff-line--added").text()).toContain("+new line");
    expect(wrapper.find(".diff-line--removed").text()).toContain("-old line");
    expect(wrapper.find(".diff-line--hunk").exists()).toBe(true);
  });
});
