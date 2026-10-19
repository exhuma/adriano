/**
 * Ensure the record page shows Accept/Reject controls only when the
 * caller `can_decide`, and otherwise shows the server's
 * `decide_blocked_reason` as visible text rather than a silently
 * disabled control (SPEC.md acceptance criteria 3, 19).
 */
import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory, createRouter, type Router } from "vue-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import vuetify from "@/plugins/vuetify";
import RecordView from "@/views/RecordView.vue";
import type { RecordDetail } from "@/types/records";
import type { RecordDiffOut } from "@/types/approval";

const getRecord = vi.fn();
const getRecordDiff = vi.fn();

vi.mock("@/api/records", () => ({
  getRecord: (...args: unknown[]) => getRecord(...args),
  getRecordDiff: (...args: unknown[]) => getRecordDiff(...args),
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
    },
    freshness: {
      last_attempt_at: null,
      last_success_at: "2026-01-01T00:00:00Z",
      last_status: "ok",
      stale: false,
    },
    outbound_links: [],
    inbound_links: [],
    errata: [],
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
    expect(wrapper.text()).toContain("sign in as a reviewer to decide");
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

    expect(wrapper.text()).toContain("Candidate from branch feature/x");
    expect(wrapper.text()).toContain(
      "Accepted — this candidate is authoritative for implementation " +
        "before publication.",
    );
  });
});
