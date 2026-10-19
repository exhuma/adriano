/**
 * Ensure the record page's provenance/freshness wording (audit
 * finding, criterion 21) depends on record kind and poll outcome:
 * a candidate is never described in terms of polling or a published
 * revision; a failed/partial poll is worded distinctly from content
 * that is merely older than the freshness threshold; and a push-only
 * registration (no `poll` intake) never shows a polling banner.
 */
import { describe, expect, it } from "vitest";

import type { FreshnessOut, ProvenanceOut } from "@/types/records";
import { freshnessBannerText, provenanceText } from "@/utils/freshness";

function provenance(overrides: Partial<ProvenanceOut> = {}): ProvenanceOut {
  return {
    source_id: "central",
    project: "platform",
    path: "doc/decisions/2026-01-01-x.md",
    ref: "main",
    source_url: null,
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function freshness(overrides: Partial<FreshnessOut> = {}): FreshnessOut {
  return {
    last_attempt_at: null,
    last_success_at: "2026-01-01T00:00:00Z",
    last_status: "ok",
    stale: false,
    intake: ["poll"],
    ...overrides,
  };
}

describe("provenanceText", () => {
  it("describes a candidate by submission branch and time, never polling", () => {
    const text = provenanceText(
      "candidate",
      provenance({ ref: "feature/x", updated_at: "2026-02-03T10:00:00Z" }),
    );
    expect(text).toContain("Submitted from branch feature/x");
    expect(text.toLowerCase()).not.toContain("poll");
    expect(text.toLowerCase()).not.toContain("published revision");
  });

  it("describes a published record by source/project", () => {
    const text = provenanceText("published", provenance());
    expect(text).toBe("Published from central / platform.");
  });
});

describe("freshnessBannerText", () => {
  it("shows no banner for a candidate", () => {
    expect(
      freshnessBannerText("candidate", provenance(), freshness({ stale: true })),
    ).toBeNull();
  });

  it("shows no banner for a push-only registration", () => {
    expect(
      freshnessBannerText(
        "published",
        provenance(),
        freshness({ stale: true, intake: ["push"] }),
      ),
    ).toBeNull();
  });

  it("shows no banner when the content is fresh", () => {
    expect(
      freshnessBannerText("published", provenance(), freshness({ stale: false })),
    ).toBeNull();
  });

  it("describes a failed poll as the last good snapshot, not merely old", () => {
    const text = freshnessBannerText(
      "published",
      provenance({ source_id: "gitlab-platform" }),
      freshness({
        stale: true,
        last_status: "failed",
        last_attempt_at: "2026-03-01T12:00:00Z",
      }),
    );
    expect(text).toContain("last poll of gitlab-platform failed");
    expect(text).toContain(
      "this is the last successfully indexed revision and may not be " +
        "the current published revision.",
    );
  });

  it("describes a partial poll distinctly from a failed one", () => {
    const text = freshnessBannerText(
      "published",
      provenance(),
      freshness({ stale: true, last_status: "partial" }),
    );
    expect(text).toContain("was incomplete");
  });

  it("describes stale-by-age content without claiming it could not be refreshed", () => {
    const text = freshnessBannerText(
      "published",
      provenance(),
      freshness({ stale: true, last_status: "ok" }),
    );
    expect(text).toContain("older than the freshness threshold");
    expect(text).toContain("the source may have changed since");
    expect(text?.toLowerCase()).not.toContain("could not be refreshed");
  });
});
