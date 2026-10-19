/**
 * Ensure the decide-flow core resolves to a typed outcome for a
 * successful decision and for every refusal the dialog must handle
 * differently: `digest_changed` (reload, no retry), `already_decided`
 * and `not_eligible` (shown with the server's own message/hint).
 * This composable never throws -- the dialog adapter branches on
 * `outcome.kind` instead of a try/catch.
 */
import { describe, expect, it, vi } from "vitest";

import { ApiError } from "@/api";
import { useDecision } from "@/composables/useDecision";
import type { DecisionSummaryOut } from "@/types/approval";

const postDecision = vi.fn();

vi.mock("@/api/decisions", () => ({
  postDecision: (...args: unknown[]) => postDecision(...args),
}));

const event: DecisionSummaryOut = {
  id: "11111111-1111-1111-1111-111111111111",
  digest: "sha256-v1:abc",
  current_digest: true,
  action: "accepted",
  actor_issuer: "https://idp.example.com",
  actor_subject: "sub-1",
  actor_display: "Alice",
  comment: null,
  policy_id: "global",
  policy_version: 1,
  provenance: {
    record_id: "r1",
    kind: "candidate",
    source_id: "central",
    project: "platform",
    ref: "feature/x",
    path: "doc/decisions/x.md",
    source_url: null,
  },
  created_at: "2026-01-01T00:00:00Z",
};

describe("useDecision", () => {
  it("resolves to a success outcome and sends the expected digest", async () => {
    postDecision.mockResolvedValue(event);
    const { decide, submitting } = useDecision();

    const promise = decide("r1", "accepted", "sha256-v1:abc", "  looks good  ");
    expect(submitting.value).toBe(true);
    const outcome = await promise;

    expect(submitting.value).toBe(false);
    expect(outcome).toEqual({ kind: "success", event });
    expect(postDecision).toHaveBeenCalledWith("r1", {
      action: "accepted",
      comment: "looks good",
      expected_digest: "sha256-v1:abc",
    });
  });

  it("omits a blank comment", async () => {
    postDecision.mockResolvedValue(event);
    const { decide } = useDecision();

    await decide("r1", "accepted", "sha256-v1:abc", "   ");

    expect(postDecision).toHaveBeenCalledWith("r1", {
      action: "accepted",
      comment: undefined,
      expected_digest: "sha256-v1:abc",
    });
  });

  it("maps 409 digest_changed to a digest_changed outcome", async () => {
    postDecision.mockRejectedValue(
      new ApiError(409, {
        detail: "the content changed since you loaded it",
        code: "digest_changed",
        hint: "reload the record, review the new content, then decide",
      }),
    );
    const { decide } = useDecision();

    const outcome = await decide("r1", "accepted", "sha256-v1:stale");

    expect(outcome.kind).toBe("digest_changed");
    expect(outcome).toMatchObject({
      message: "the content changed since you loaded it",
    });
  });

  it("maps 409 already_decided to a generic error outcome with its hint", async () => {
    postDecision.mockRejectedValue(
      new ApiError(409, {
        detail: "a decision for this exact content already exists",
        code: "already_decided",
        hint: "reload the record to see the recorded decision",
      }),
    );
    const { decide } = useDecision();

    const outcome = await decide("r1", "accepted", "sha256-v1:abc");

    expect(outcome).toEqual({
      kind: "error",
      code: "already_decided",
      message: "a decision for this exact content already exists",
      hint: "reload the record to see the recorded decision",
    });
  });

  it("maps 403 not_eligible to a generic error outcome", async () => {
    postDecision.mockRejectedValue(
      new ApiError(403, {
        detail: "you are not an eligible reviewer",
        code: "not_eligible",
        hint: "ask an operator to list you or one of your roles",
      }),
    );
    const { decide } = useDecision();

    const outcome = await decide("r1", "rejected", "sha256-v1:abc");

    expect(outcome).toEqual({
      kind: "error",
      code: "not_eligible",
      message: "you are not an eligible reviewer",
      hint: "ask an operator to list you or one of your roles",
    });
  });

  it("falls back to a generic message for a network failure", async () => {
    postDecision.mockRejectedValue(new TypeError("network down"));
    const { decide } = useDecision();

    const outcome = await decide("r1", "accepted", "sha256-v1:abc");

    expect(outcome.kind).toBe("error");
    expect((outcome as { message: string }).message).toContain(
      "could not be recorded",
    );
  });
});
