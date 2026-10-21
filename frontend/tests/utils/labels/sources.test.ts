/**
 * Ensure the source/registration view-model helpers keep staleness as
 * secondary text (never a second chip) and give every poll/config
 * problem code a plain-language headline. Split from the former
 * `tests/utils/labels.test.ts` to mirror `src/utils/labels/sources.ts`
 * (module-code-structure-limits).
 */
import { describe, expect, it } from "vitest";

import {
  configErrorLabel,
  pollProblemLabel,
  pollStatusLabel,
  staleStatusText,
} from "@/utils/labels";
import type { ConfigErrorCode, PollStatus } from "@/types/sources";

describe("pollStatusLabel", () => {
  it.each([
    ["never", "Never polled"],
    ["ok", "OK"],
    ["partial", "Partial"],
    ["failed", "Failed"],
    ["disabled", "Disabled"],
  ] as [PollStatus, string][])(
    "labels %s as %s when not stale",
    (status, expected) => {
      expect(pollStatusLabel(status, false).text).toBe(expected);
    },
  );

  it("shifts icon and colour, but not text, for a stale non-failed " +
    "status (docs/ui-review O-01: staleness is secondary text, not a " +
    "second chip or a suffix on this one)", () => {
    const label = pollStatusLabel("ok", true);
    expect(label.text).toBe("OK");
    expect(label.color).toBe("warning");
    expect(label.icon).toBe("mdi-clock-alert-outline");
  });

  it("does not duplicate the failure state when stale and failed", () => {
    const label = pollStatusLabel("failed", true);
    expect(label.text).toBe("Failed");
    expect(label.color).toBe("error");
  });
});

describe("staleStatusText", () => {
  it("returns null when not stale", () => {
    expect(staleStatusText("ok", false)).toBeNull();
  });

  it("returns null for a failed poll (the chip already explains it)", () => {
    expect(staleStatusText("failed", true)).toBeNull();
  });

  it("returns a secondary stale note for any other stale status", () => {
    expect(staleStatusText("disabled", true)).toContain("Stale");
    expect(staleStatusText("ok", true)).toContain("Stale");
    expect(staleStatusText("never", true)).toContain("Stale");
  });
});

describe("pollProblemLabel", () => {
  const codes = [
    "source_error",
    "internal_error",
    "projects_incomplete",
    "listing_failed",
    "listing_incomplete",
    "fetch_failed",
    "ownership_conflict",
    "not_pollable",
  ];

  it.each(codes)(
    "gives a non-empty headline for every known code: %s",
    (code) => {
      expect(pollProblemLabel(code)?.length).toBeGreaterThan(0);
    },
  );

  it("returns null for an unrecognised code", () => {
    expect(pollProblemLabel("some_future_code")).toBeNull();
  });

  it("returns null for a missing code", () => {
    expect(pollProblemLabel(undefined)).toBeNull();
  });
});

describe("configErrorLabel", () => {
  const codes: ConfigErrorCode[] = [
    "invalid_settings",
    "unknown_type",
    "type_unavailable",
    "invalid_published_ref",
    "token_env_missing",
    "removed_from_config",
    "other",
  ];

  it.each(codes)(
    "gives a plain-language headline for every code: %s",
    (code) => {
      const headline = configErrorLabel(code);
      expect(headline?.length).toBeGreaterThan(0);
      // Never the raw machine code itself.
      expect(headline).not.toContain(code);
    },
  );

  it("returns null when the backend sent no code", () => {
    expect(configErrorLabel(null)).toBeNull();
  });
});
