/**
 * Ensure the record page shows Accept/Reject controls only when the
 * caller `can_decide`, and otherwise shows the server's
 * `decide_blocked_reason` as visible text rather than a silently
 * disabled control.
 */
import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory, createRouter, type Router } from "vue-router";
import { ref } from "vue";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import vuetify from "@/plugins/vuetify";
import RecordView from "@/views/RecordView.vue";
import type { RecordDetail } from "@/types/records";
import type { DecisionOutcome } from "@/composables/useDecision";
import type { DecisionSummaryOut, RecordDiffOut } from "@/types/approval";

const getRecord = vi.fn();
const getRecordDiff = vi.fn();

vi.mock("@/api/records", () => ({
  getRecord: (...args: unknown[]) => getRecord(...args),
  getRecordDiff: (...args: unknown[]) => getRecordDiff(...args),
}));

// Same approach as `DecisionDialog.test.ts`: mock the delivery-agnostic
// decide composable directly so the decided/digest-changed flow can be
// driven without a real decisions endpoint.
const decide = vi.fn<(...args: unknown[]) => Promise<DecisionOutcome>>();

vi.mock("@/composables/useDecision", () => ({
  useDecision: () => ({ submitting: ref(false), decide }),
}));

const noPriorDiff: RecordDiffOut = {
  base: null,
  target: { digest: "sha256-v1:abc", label: "current revision", decided_at: null },
  reason: "no_prior_revision",
  unified_diff: "",
  identical: false,
  lines_added: 0,
  lines_removed: 0,
};

function baseDetail(): RecordDetail {
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
  };
}

function makeRouter(): Promise<Router> {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/records/:id", name: "record", component: RecordView, props: true },
    ],
  });
  return router.push("/records/11111111-1111-1111-1111-111111111111").then(() =>
    router.isReady().then(() => router),
  );
}

async function mountRecordView() {
  const router = await makeRouter();
  const wrapper = mount(RecordView, {
    props: { id: "11111111-1111-1111-1111-111111111111" },
    global: { plugins: [router, vuetify] },
  });
  await flushPromises();
  return wrapper;
}

describe("RecordView approval controls", () => {
  beforeEach(() => {
    getRecordDiff.mockResolvedValue(noPriorDiff);
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  it("shows Accept/Reject buttons when the caller can decide", async () => {
    getRecord.mockResolvedValue(baseDetail());

    const wrapper = await mountRecordView();

    const buttons = wrapper.findAll("button").map((b) => b.text());
    expect(buttons).toContain("Accept");
    expect(buttons).toContain("Reject");
    expect(wrapper.text()).not.toContain("sign in as a reviewer");
  });

  it("shows the blocked reason as visible text, never a disabled control, when the caller cannot decide", async () => {
    const detail = baseDetail();
    detail.approval.can_decide = false;
    detail.approval.decide_blocked_code = "anonymous";
    detail.approval.decide_blocked_reason = "sign in as a reviewer to decide";
    getRecord.mockResolvedValue(detail);

    const wrapper = await mountRecordView();

    const buttons = wrapper.findAll("button").map((b) => b.text());
    expect(buttons).not.toContain("Accept");
    expect(buttons).not.toContain("Reject");
    // The raw backend reason is replaced with plain-language copy
    // for the stable blocker code.
    expect(wrapper.text()).toContain("Sign in as a reviewer to decide this.");
    expect(wrapper.text()).not.toContain("sign in as a reviewer to decide");
  });

  it("explains an unconfigured policy distinctly from a pending review", async () => {
    const detail = baseDetail();
    detail.approval.state = "policy_missing";
    detail.approval.policy = {
      status: "missing",
      id: null,
      version: null,
      required: null,
      allow_self_approval: null,
    };
    detail.approval.can_decide = false;
    detail.approval.decide_blocked_code = "policy_missing";
    detail.approval.decide_blocked_reason =
      "the approval policy is not configured or invalid; decisions are refused";
    getRecord.mockResolvedValue(detail);

    const wrapper = await mountRecordView();

    expect(wrapper.text()).toContain(
      "No approval policy is configured — an operator must configure one.",
    );
  });

  it("distinguishes candidate provenance and labels an accepted candidate", async () => {
    const detail = baseDetail();
    detail.approval.state = "accepted";
    getRecord.mockResolvedValue(detail);

    const wrapper = await mountRecordView();

    expect(wrapper.text()).toContain("Submitted from branch feature/x");
    expect(wrapper.text()).toContain(
      "Accepted — this candidate is authoritative for implementation " +
        "before publication.",
    );
  });
});

describe("RecordView freshness banner", () => {
  beforeEach(() => {
    getRecordDiff.mockResolvedValue(noPriorDiff);
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  it("never shows a polling-freshness banner for a candidate", async () => {
    const detail = baseDetail();
    detail.freshness.stale = true;
    detail.freshness.last_status = "failed";
    getRecord.mockResolvedValue(detail);

    const wrapper = await mountRecordView();

    expect(wrapper.text()).not.toContain("may not be the current published");
    expect(wrapper.text()).not.toContain("older than the freshness threshold");
  });

  it("describes a failed poll distinctly from merely old content for a published record", async () => {
    const detail = baseDetail();
    detail.metadata.kind = "published";
    detail.freshness.stale = true;
    detail.freshness.last_status = "failed";
    detail.freshness.last_attempt_at = "2026-03-01T12:00:00Z";
    getRecord.mockResolvedValue(detail);

    const wrapper = await mountRecordView();

    expect(wrapper.text()).toContain("The last poll of central failed");
    expect(wrapper.text()).toContain(
      "this is the last successfully indexed revision and may not be " +
        "the current published revision.",
    );
    expect(wrapper.text()).not.toContain("could not be refreshed");
  });

  it("describes stale-by-age content without claiming the poll failed", async () => {
    const detail = baseDetail();
    detail.metadata.kind = "published";
    detail.freshness.stale = true;
    detail.freshness.last_status = "ok";
    getRecord.mockResolvedValue(detail);

    const wrapper = await mountRecordView();

    expect(wrapper.text()).toContain("older than the freshness threshold");
    expect(wrapper.text()).toContain("the source may have changed since");
    expect(wrapper.text()).not.toContain("the last poll of");
  });

  it("shows no polling-freshness banner for a push-only registration", async () => {
    const detail = baseDetail();
    detail.metadata.kind = "published";
    detail.freshness.stale = true;
    detail.freshness.last_status = "ok";
    detail.freshness.intake = ["push"];
    getRecord.mockResolvedValue(detail);

    const wrapper = await mountRecordView();

    expect(wrapper.text()).not.toContain("older than the freshness threshold");
    expect(wrapper.text()).not.toContain("the last poll of");
  });
});

describe("RecordView legacy sign-off card", () => {
  beforeEach(() => {
    getRecordDiff.mockResolvedValue(noPriorDiff);
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  it("shows the legacy sign-off card, separate from the approval card, with its explanation", async () => {
    const detail = baseDetail();
    detail.legacy_signoff_unverified = ["Jane Doe <jane@example.com>"];
    getRecord.mockResolvedValue(detail);

    const wrapper = await mountRecordView();

    expect(wrapper.text()).toContain("Legacy sign-off (unverified)");
    expect(wrapper.text()).toContain("signed-off-by");
    expect(wrapper.text()).toContain("not a verified approval");
    expect(wrapper.text()).toContain("Jane Doe <jane@example.com>");
    // Separate from the approval card: the approval card's own
    // heading is still present and distinct from this one.
    expect(wrapper.text()).toContain("Approval");
  });

  it("does not render the legacy sign-off card when there is nothing legacy", async () => {
    const detail = baseDetail();
    detail.legacy_signoff_unverified = [];
    getRecord.mockResolvedValue(detail);

    const wrapper = await mountRecordView();

    expect(wrapper.text()).not.toContain("Legacy sign-off (unverified)");
  });
});

describe("RecordView status banners and layout", () => {
  beforeEach(() => {
    getRecordDiff.mockResolvedValue(noPriorDiff);
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  it("shows the obsoleted lifecycle notice from the derived status and an inbound obsoleted_by link", async () => {
    const detail = baseDetail();
    detail.status = "obsoleted";
    detail.inbound_links = [
      { link_type: "obsoleted_by", source_id: "33333333-3333-3333-3333-333333333333", source_title: "Use gRPC" },
    ];
    getRecord.mockResolvedValue(detail);

    const wrapper = await mountRecordView();

    expect(wrapper.text()).toContain("This decision is obsolete, see");
    expect(wrapper.text()).toContain("Use gRPC");
  });

  it("hides the sidebar's 'Referenced by' entry the lifecycle notice " +
    "already states, but keeps one it does not (P11-R-21)", async () => {
    const detail = baseDetail();
    detail.status = "obsoleted";
    detail.inbound_links = [
      {
        link_type: "obsoleted_by",
        source_id: "33333333-3333-3333-3333-333333333333",
        source_title: "Use gRPC",
      },
      {
        link_type: "updated_by",
        source_id: "44444444-4444-4444-4444-444444444444",
        source_title: "Use PostgreSQL v2",
      },
    ];
    getRecord.mockResolvedValue(detail);

    const wrapper = await mountRecordView();

    expect(wrapper.text()).toContain("This decision is obsolete, see");
    const sidebar = wrapper.find("aside");
    // The obsoleted_by link is already stated by the banner above,
    // so the sidebar's "Referenced by" card never repeats it.
    expect(sidebar.text()).not.toContain("Obsoleted by");
    expect(sidebar.text()).not.toContain("Use gRPC");
    // The coexisting updated_by link is not stated by the banner
    // (obsoleted takes priority there), so it still appears once.
    expect(sidebar.text()).toContain("Updated by");
    expect(sidebar.text()).toContain("Use PostgreSQL v2");
  });

  it("shows the updated lifecycle notice from the derived status and an inbound updated_by link", async () => {
    const detail = baseDetail();
    detail.status = "updated";
    detail.inbound_links = [
      { link_type: "updated_by", source_id: "33333333-3333-3333-3333-333333333333", source_title: "Use PostgreSQL v2" },
    ];
    getRecord.mockResolvedValue(detail);

    const wrapper = await mountRecordView();

    expect(wrapper.text()).toContain("This decision was updated, see");
    expect(wrapper.text()).toContain("Use PostgreSQL v2");
  });

  it("shows the errata count as a header link, with a working #errata anchor below (R-04)", async () => {
    const detail = baseDetail();
    detail.errata_summary = {
      total: 1,
      verified: 0,
      reported: 1,
      rejected: 0,
      changed: 0,
      proposed: 0,
    };
    detail.errata = [
      {
        id: "44444444-4444-4444-4444-444444444444",
        kind: "published",
        ref: "main",
        source_id: "central",
        project: "platform",
        path: "doc/decisions/errata/2025-05-01-fix.md",
        title: "Erratum: Consequences",
        type: "technical",
        section: "Consequences",
        reported_by: null,
        reported_date: null,
        original_html: null,
        corrected_html: "<p>fixed</p>",
        notes_html: null,
        approval_state: "pending",
        approvable: true,
        digest: "sha256-v1:def",
        updated_at: "2026-01-01T00:00:00Z",
        has_content: true,
      },
    ];
    getRecord.mockResolvedValue(detail);

    const wrapper = await mountRecordView();

    const headerLink = wrapper.find("a[href='#errata']");
    expect(headerLink.exists()).toBe(true);
    expect(headerLink.text()).toBe("View errata");
    expect(wrapper.text()).toContain("1 erratum");
    const anchorTarget = wrapper.find("#errata");
    expect(anchorTarget.exists()).toBe(true);
    expect(anchorTarget.text()).toContain("Reported");
    expect(anchorTarget.text()).toContain("Technical");
    expect(anchorTarget.text()).toContain("Section: Consequences");
  });

  it("shows the erratum-for banner on an erratum page, resolved to its target, with the erratum's own status", async () => {
    const detail = baseDetail();
    detail.metadata.record_kind = "erratum";
    detail.approval.state = "accepted";
    detail.erratum_for = {
      uuid: "55555555-5555-5555-5555-555555555555",
      id: "66666666-6666-6666-6666-666666666666",
      title: "Use PostgreSQL",
      resolved: true,
    };
    getRecord.mockResolvedValue(detail);

    const wrapper = await mountRecordView();

    expect(wrapper.text()).toContain("This is an erratum for");
    expect(wrapper.text()).toContain("Use PostgreSQL");
    expect(wrapper.text()).toContain("Erratum");
    // The erratum's own status (accepted = "Verified"), not the
    // target's -- and not the plain decision wording.
    expect(wrapper.text()).toContain("Verified");
  });

  it("titles the page 'Erratum for <target>' (h1) once the erratum's target resolves", async () => {
    const detail = baseDetail();
    detail.metadata.record_kind = "erratum";
    detail.metadata.title = "Erratum: Consequences";
    detail.erratum_for = {
      uuid: "55555555-5555-5555-5555-555555555555",
      id: "66666666-6666-6666-6666-666666666666",
      title: "Use PostgreSQL",
      resolved: true,
    };
    getRecord.mockResolvedValue(detail);

    const wrapper = await mountRecordView();

    expect(wrapper.find("h1").text()).toBe("Erratum for Use PostgreSQL");
  });

  it("keeps the erratum's own stored title as the h1 when the target is unresolved", async () => {
    const detail = baseDetail();
    detail.metadata.record_kind = "erratum";
    detail.metadata.title = "Erratum: orphaned";
    detail.erratum_for = {
      uuid: "55555555-5555-5555-5555-555555555555",
      id: null,
      title: null,
      resolved: false,
    };
    getRecord.mockResolvedValue(detail);

    const wrapper = await mountRecordView();

    expect(wrapper.find("h1").text()).toBe("Erratum: orphaned");
  });

  it("hides the Diff card when there is no prior revision (R-08)", async () => {
    getRecord.mockResolvedValue(baseDetail());

    const wrapper = await mountRecordView();

    const headings = wrapper.findAll("h2").map((h) => h.text());
    expect(headings).not.toContain("Diff");
    expect(getRecordDiff).not.toHaveBeenCalled();
    expect(wrapper.text()).not.toContain("No prior revision");
  });

  it("shows the Diff card when a prior revision exists", async () => {
    const detail = baseDetail();
    detail.metadata.previous_digest = "sha256-v1:old";
    getRecord.mockResolvedValue(detail);

    const wrapper = await mountRecordView();

    const headings = wrapper.findAll("h2").map((h) => h.text());
    expect(headings).toContain("Diff");
    expect(getRecordDiff).toHaveBeenCalled();
  });

  it("offers Accept/Reject in the sidebar and the approval card", async () => {
    getRecord.mockResolvedValue(baseDetail());

    const wrapper = await mountRecordView();

    const sidebar = wrapper.find("aside");
    const sidebarButtons = sidebar.findAll("button").map((b) => b.text());
    expect(sidebarButtons).toEqual(
      expect.arrayContaining(["Accept", "Reject"]),
    );
    const accepts = wrapper
      .findAll("button")
      .filter((b) => b.text() === "Accept");
    expect(accepts).toHaveLength(2);
  });

  it("orders headings h1 > h2 sections/sidebar > h3 cards (G-05)", async () => {
    const detail = baseDetail();
    detail.issues = [
      {
        code: "obsolete_kind_field",
        severity: "warning",
        message: "something",
      },
    ];
    getRecord.mockResolvedValue(detail);

    const wrapper = await mountRecordView();

    expect(wrapper.findAll("h1")).toHaveLength(1);
    const h2s = wrapper.findAll("h2").map((h) => h.text());
    expect(h2s).toEqual(
      expect.arrayContaining([
        "Validation issues",
        "Approval",
        "About this decision",
      ]),
    );
    for (const h2 of wrapper.findAll("h2")) {
      expect(h2.classes()).toContain("text-title-large");
    }
    const h3s = wrapper.findAll("aside h3").map((h) => h.text());
    expect(h3s).toContain("Metadata");
    expect(h3s).toContain("Provenance");
  });

  it("puts the sidebar's metadata after the main column in document order", async () => {
    getRecord.mockResolvedValue(baseDetail());

    const wrapper = await mountRecordView();

    const html = wrapper.html();
    expect(html.indexOf("Approval")).toBeLessThan(html.indexOf("About this decision"));
  });
});

describe("RecordView post-decision refresh (P11-R-16)", () => {
  function decisionEvent(
    action: DecisionSummaryOut["action"],
  ): DecisionSummaryOut {
    return {
      id: "77777777-7777-7777-7777-777777777777",
      digest: "sha256-v1:abc",
      current_digest: true,
      action,
      actor_issuer: "https://idp.example",
      actor_subject: "user-1",
      actor_display: "Jane Reviewer",
      comment: null,
      policy_id: "global",
      policy_version: 1,
      provenance: {
        record_id: "11111111-1111-1111-1111-111111111111",
        kind: "published",
        source_id: null,
        project: null,
        ref: null,
        path: null,
        source_url: null,
      },
      created_at: "2026-01-01T00:00:00Z",
    };
  }

  /** The two page-level Accept/Reject triggers (sidebar + approval
   *  card) are plain buttons on `document.body` once attached; the
   *  dialog's own submit button is scoped out via its `v-card-actions`
   *  wrapper (unique to `DecisionDialog`) so clicking it never
   *  re-opens a trigger instead of submitting. */
  function findButton(text: string): HTMLButtonElement | undefined {
    return Array.from(document.body.querySelectorAll("button")).find(
      (b) => b.textContent?.trim() === text,
    );
  }

  function dialogButton(text: string): HTMLButtonElement | undefined {
    return Array.from(
      document.body.querySelectorAll<HTMLButtonElement>(
        ".v-card-actions button",
      ),
    ).find((b) => b.textContent?.trim() === text);
  }

  async function mountAttached() {
    const router = await makeRouter();
    const wrapper = mount(RecordView, {
      props: { id: "11111111-1111-1111-1111-111111111111" },
      global: { plugins: [router, vuetify] },
      attachTo: document.body,
    });
    await flushPromises();
    return wrapper;
  }

  afterEach(() => {
    vi.clearAllMocks();
    document.body.innerHTML = "";
  });

  it("refreshes in place after a decision -- no loading-state remount, " +
    "and focus moves to the sidebar status heading", async () => {
    getRecord.mockResolvedValueOnce(baseDetail());
    getRecord.mockResolvedValueOnce(baseDetail());
    decide.mockResolvedValueOnce({
      kind: "success",
      event: decisionEvent("accepted"),
    });

    const wrapper = await mountAttached();

    findButton("Accept")!.click();
    await flushPromises();
    dialogButton("Accept")!.click();
    await flushPromises();
    await flushPromises();

    expect(getRecord).toHaveBeenCalledTimes(2);
    // The page content stayed mounted throughout -- it never fell
    // back to the loading state and lost the already-rendered record.
    expect(wrapper.text()).not.toContain("Loading record");
    expect(wrapper.find("h1").exists()).toBe(true);
    expect(wrapper.text()).toContain("Use PostgreSQL");
    // `v-snackbar` teleports its content to `document.body`, outside
    // the wrapper's own element (same as `v-dialog`; see
    // `DecisionDialog.test.ts`).
    expect(document.body.textContent).toContain("Decision recorded: accepted.");
    // Focus lands on the sidebar's status heading, a `tabindex="-1"`
    // target, instead of staying on a trigger button that may have
    // disappeared or resetting to the document body.
    expect(document.activeElement?.id).toBe("sidebar-heading");
  });

  it("discards a stale refresh when a newer decision's refresh " +
    "already started (P11-R-16)", async () => {
    getRecord.mockResolvedValueOnce(baseDetail()); // initial load

    let resolveStale!: (detail: RecordDetail) => void;
    let resolveFresh!: (detail: RecordDetail) => void;
    getRecord.mockImplementationOnce(
      () => new Promise<RecordDetail>((resolve) => (resolveStale = resolve)),
    );
    getRecord.mockImplementationOnce(
      () => new Promise<RecordDetail>((resolve) => (resolveFresh = resolve)),
    );
    decide
      .mockResolvedValueOnce({
        kind: "success",
        event: decisionEvent("accepted"),
      })
      .mockResolvedValueOnce({
        kind: "success",
        event: decisionEvent("rejected"),
      });

    await mountAttached();

    // First decision starts a refresh that will not resolve yet.
    findButton("Accept")!.click();
    await flushPromises();
    dialogButton("Accept")!.click();
    await flushPromises();

    // `detail.value` has not changed yet (the first refresh is still
    // pending), so a second decision can start -- and start a newer
    // refresh -- before the first one resolves.
    findButton("Accept")!.click();
    await flushPromises();
    dialogButton("Accept")!.click();
    await flushPromises();

    const staleDetail = baseDetail();
    staleDetail.metadata.title = "Stale title";
    const freshDetail = baseDetail();
    freshDetail.metadata.title = "Fresh title";

    // Resolve the newer request first, then the stale one: the stale
    // response must never overwrite the fresher one already applied.
    resolveFresh(freshDetail);
    await flushPromises();
    resolveStale(staleDetail);
    await flushPromises();

    expect(document.body.textContent).toContain("Fresh title");
    expect(document.body.textContent).not.toContain("Stale title");
  });
});
