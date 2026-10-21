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
  recoveryHint,
  staleStatusText,
} from "@/utils/labels";
import type { ConfigErrorCode, PollStatus } from "@/types/sources";
import type { SourceProblemDisplay } from "@/utils/sourceErrors";

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

describe("recoveryHint", () => {
  const configCodes: ConfigErrorCode[] = [
    "invalid_settings",
    "unknown_type",
    "type_unavailable",
    "invalid_published_ref",
    "token_env_missing",
    "removed_from_config",
    "other",
  ];

  it.each(configCodes)(
    "gives a non-empty hint for every config error code: %s",
    (code) => {
      const problem: SourceProblemDisplay = { kind: "config", code, text: "x" };
      expect(recoveryHint(problem, "gitlab")?.length).toBeGreaterThan(0);
    },
  );

  it("never tells the operator to check a token env var for " +
    "removed_from_config", () => {
    const problem: SourceProblemDisplay = {
      kind: "config",
      code: "removed_from_config",
      text: "x",
    };
    const hint = recoveryHint(problem, "gitlab");
    expect(hint).not.toContain("token env var");
    expect(hint).toContain("catalog.yaml");
  });

  it("mentions the token env var only for token_env_missing", () => {
    const problem: SourceProblemDisplay = {
      kind: "config",
      code: "token_env_missing",
      text: "x",
    };
    expect(recoveryHint(problem, "gitlab")).toContain(
      "access token's environment variable",
    );
  });

  it("falls back to a source-type hint for an unrecognised config " +
    "code (null)", () => {
    const problem: SourceProblemDisplay = {
      kind: "config",
      code: null,
      text: "x",
    };
    expect(recoveryHint(problem, "gitlab")).toContain("catalog.yaml");
  });

  it("gives a non-empty hint for every known poll-problem code, " +
    "except not_pollable which needs no fix", () => {
    const codes = [
      "source_error",
      "internal_error",
      "projects_incomplete",
      "listing_failed",
      "listing_incomplete",
      "fetch_failed",
      "ownership_conflict",
    ];
    for (const code of codes) {
      const problem: SourceProblemDisplay = {
        kind: "list",
        items: [{ code, message: "x" }],
      };
      expect(recoveryHint(problem, "gitlab")?.length).toBeGreaterThan(0);
    }

    const notPollable: SourceProblemDisplay = {
      kind: "list",
      items: [{ code: "not_pollable", message: "x" }],
    };
    expect(recoveryHint(notPollable, "gitlab")).toBeNull();
  });

  it("falls back to a source-type hint for an unrecognised " +
    "poll-problem code", () => {
    const problem: SourceProblemDisplay = {
      kind: "list",
      items: [{ code: "some_future_code", message: "x" }],
    };
    expect(recoveryHint(problem, "filesystem")).toContain("root path");
  });

  it("falls back to a source-type hint for a text-kind problem " +
    "with no code at all", () => {
    const problem: SourceProblemDisplay = { kind: "text", text: "x" };
    expect(recoveryHint(problem, "filesystem")).toContain("root path");
    expect(recoveryHint(problem, "gitlab")).toContain("token env var");
  });

  it("recommends nothing for a healthy row", () => {
    const problem: SourceProblemDisplay = { kind: "none" };
    expect(recoveryHint(problem, "gitlab")).toBeNull();
  });
});
