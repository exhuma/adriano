/**
 * Ensure `useRecordDetailView`'s pure helpers and computeds behave
 * correctly: the decided-snackbar wording distinguishes an erratum
 * from a decision, the load-error text distinguishes "forbidden"
 * from a generic failure, the page title switches to "Erratum for
 * <target>" only once a resolved erratum's target is known (with a
 * section subtitle), and the accepted-candidate note and inbound-link
 * filters are unaffected by record kind.
 */
import { defineComponent, h, ref } from "vue";
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import { ApiError } from "@/api";
import {
  decidedSnackbarText,
  describeRecordLoadError,
  useRecordDetailView,
} from "@/composables/useRecordDetailView";
import type { RecordDetail } from "@/types/records";

function baseDetail(overrides: Partial<RecordDetail> = {}): RecordDetail {
  return {
    metadata: {
      id: "11111111-1111-1111-1111-111111111111",
      adr_uuid: "22222222-2222-2222-2222-222222222222",
      decision_date: "2024-12-24",
      decision_date_inferred: false,
      kind: "candidate",
      record_kind: "decision",
      title: "Use PostgreSQL",
      title_source: "frontmatter",
      digest: "sha256-v1:abc",
      previous_digest: null,
    },
    issues: [],
    rendered_html: "<p>Body</p>",
    provenance: {
      source_id: "central",
      project: "platform",
      path: "doc/decisions/2024-12-24-use-postgres.md",
      ref: "feature/x",
      source_url: null,
      updated_at: "2026-02-03T10:00:00Z",
    },
    freshness: {
      last_attempt_at: null,
      last_success_at: "2026-01-01T00:00:00Z",
      last_status: "ok",
      stale: false,
      intake: ["poll"],
    },
    outbound_links: [],
    inbound_links: [],
    errata: [],
    errata_summary: {
      total: 0,
      verified: 0,
      reported: 0,
      rejected: 0,
      changed: 0,
      proposed: 0,
    },
    erratum: null,
    erratum_for: null,
    status: "active",
    siblings: [],
    legacy_signoff_unverified: [],
    approval: {
      state: "pending",
      needs_approval: true,
      digest: "sha256-v1:abc",
      policy: {
        status: "configured",
        id: "global",
        version: 1,
        required: true,
        allow_self_approval: false,
      },
      history: [],
      approvable: true,
      approval_blocker: null,
      last_accepted_digest: null,
      can_decide: true,
      decide_blocked_code: null,
      decide_blocked_reason: null,
      divergence: null,
      competing_candidates: [],
    },
    ...overrides,
  };
}

/** Mount a probe component so the composable's `computed`s run
 *  inside Vue's reactivity system. */
function mountView(initial: RecordDetail | null) {
  const detail = ref<RecordDetail | null>(initial);
  let view!: ReturnType<typeof useRecordDetailView>;
  const Probe = defineComponent({
    setup() {
      view = useRecordDetailView(detail);
      return () => h("div");
    },
  });
  mount(Probe);
  return { detail, view };
}

describe("decidedSnackbarText", () => {
  it("uses erratum wording for an erratum", () => {
    expect(decidedSnackbarText("accepted", true)).toBe("Erratum verified.");
    expect(decidedSnackbarText("rejected", true)).toBe("Erratum rejected.");
  });

  it("uses plain decision wording for a decision", () => {
    expect(decidedSnackbarText("accepted", false)).toBe("Decision recorded: accepted.");
    expect(decidedSnackbarText("rejected", false)).toBe("Decision recorded: rejected.");
  });
});

describe("describeRecordLoadError", () => {
  it("describes a forbidden error distinctly", () => {
    const error = new ApiError(403, { detail: "the 'read' permission is required" });
    expect(describeRecordLoadError(error)).toBe("the 'read' permission is required");
  });

  it("describes a generic ApiError with its status", () => {
    const error = new ApiError(500, null);
    expect(describeRecordLoadError(error)).toContain("status 500");
  });

  it("describes a non-ApiError failure generically", () => {
    expect(describeRecordLoadError(new Error("network down"))).toBe(
      "The record could not be loaded. Check your connection and try again.",
    );
  });
});

describe("useRecordDetailView page title/subtitle", () => {
  it("uses the record's own title for an ordinary decision", () => {
    const { view } = mountView(baseDetail());

    expect(view.pageTitle.value).toBe("Use PostgreSQL");
    expect(view.pageSubtitle.value).toBeNull();
  });

  it("switches to 'Erratum for <target>' once the target resolves, with a section subtitle", () => {
    const { view } = mountView(
      baseDetail({
        metadata: {
          ...baseDetail().metadata,
          record_kind: "erratum",
          title: "Erratum: Consequences",
        },
        erratum: {
          type: "technical",
          section: "Consequences",
          reported_by: null,
          reported_date: null,
          original_html: null,
          corrected_html: "<p>fixed</p>",
          notes_html: null,
        },
        erratum_for: {
          uuid: "33333333-3333-3333-3333-333333333333",
          id: "44444444-4444-4444-4444-444444444444",
          title: "Use PostgreSQL",
          resolved: true,
        },
      }),
    );

    expect(view.pageTitle.value).toBe("Erratum for Use PostgreSQL");
    expect(view.pageSubtitle.value).toBe("Section: Consequences");
  });

  it("keeps the erratum's own stored title when the target is unresolved", () => {
    const { view } = mountView(
      baseDetail({
        metadata: {
          ...baseDetail().metadata,
          record_kind: "erratum",
          title: "Erratum: orphaned",
        },
        erratum_for: {
          uuid: "33333333-3333-3333-3333-333333333333",
          id: null,
          title: null,
          resolved: false,
        },
      }),
    );

    expect(view.pageTitle.value).toBe("Erratum: orphaned");
    expect(view.pageSubtitle.value).toBeNull();
  });
});

describe("useRecordDetailView accepted-candidate note and link filters", () => {
  it("flags an accepted candidate regardless of record kind", () => {
    const { view } = mountView(
      baseDetail({
        metadata: { ...baseDetail().metadata, kind: "candidate", record_kind: "erratum" },
        approval: { ...baseDetail().approval, state: "accepted" },
      }),
    );

    expect(view.showAcceptedCandidateNote.value).toBe(true);
  });

  it("filters inbound links into obsoleted/updated buckets", () => {
    const { view } = mountView(
      baseDetail({
        inbound_links: [
          { link_type: "obsoleted_by", source_id: "aaa", source_title: "Use gRPC" },
          { link_type: "updated_by", source_id: "bbb", source_title: "Use PostgreSQL v2" },
        ],
      }),
    );

    expect(view.obsoletedByLinks.value).toHaveLength(1);
    expect(view.updatedByLinks.value).toHaveLength(1);
    expect(view.obsoletedByLinks.value[0].source_id).toBe("aaa");
    expect(view.updatedByLinks.value[0].source_id).toBe("bbb");
  });
});
