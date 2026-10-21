/**
 * Source/registration view-model helpers: the poll-status chip, its
 * secondary staleness text, plain-language headlines for poll
 * problems and source configuration errors, and a per-problem
 * recovery hint (operator-only detail; decision 3, Task 8; Batch A4
 * follow-up for the hint). Split from the former `utils/labels.ts` by
 * domain (module-code-structure-limits); see `index.ts`.
 */
import type { ConfigErrorCode, PollStatus } from "@/types/sources";
import type { SourceProblemDisplay } from "@/utils/sourceErrors";

import type { StatusLabel } from "./shared";

/**
 * Describe a registration's last poll outcome for display.
 *
 * Staleness is *not* folded into this chip's text (docs/ui-review
 * O-01: a stale, disabled registration used to render "Disabled
 * (stale)" here, plus a second, fully redundant "Disabled" chip
 * derived from the raw `enabled` flag next to it -- two chips for
 * one state). The icon and colour still shift to the stale pair so
 * the chip alone is never ambiguous for someone going by icon/colour
 * only; the word itself is carried by {@link staleStatusText} as
 * secondary text next to the chip, not a second chip.
 *
 * :param status: Outcome of the latest poll.
 * :param stale: Whether freshness has crossed the configured
 *     threshold (or the registration is disabled/never succeeded).
 * :returns: Icon, label text, and colour -- one chip's worth.
 */
export function pollStatusLabel(
  status: PollStatus,
  stale: boolean,
): StatusLabel {
  const base = ((): StatusLabel => {
    switch (status) {
      case "never":
        return { icon: "mdi-help-circle-outline", text: "Never polled" };
      case "ok":
        return { icon: "mdi-check-circle", text: "OK", color: "success" };
      case "partial":
        return { icon: "mdi-alert", text: "Partial", color: "warning" };
      case "failed":
        return { icon: "mdi-close-circle", text: "Failed", color: "error" };
      case "disabled":
        return { icon: "mdi-cancel", text: "Disabled" };
      default:
        return { icon: "mdi-help-circle-outline", text: status };
    }
  })();
  if (stale && status !== "failed") {
    return { ...base, icon: "mdi-clock-alert-outline", color: "warning" };
  }
  return base;
}

/**
 * Secondary, muted text reporting staleness next to a registration's
 * status chip (docs/ui-review O-01), instead of a second chip or a
 * suffix folded into the status chip's own text.
 *
 * :param status: Outcome of the latest poll.
 * :param stale: Whether freshness has crossed the configured
 *     threshold.
 * :returns: A short note, or `null` when there is nothing to add (not
 *     stale, or a failed poll already explains the age).
 */
export function staleStatusText(
  status: PollStatus,
  stale: boolean,
): string | null {
  if (!stale || status === "failed") {
    return null;
  }
  return "Stale — past the freshness threshold.";
}

/** Stable poll-problem codes (`PollProblem.code`; see
 *  `backend/app/services/polling.py` and `poll_plan.py`), mapped to a
 *  plain-language headline. The field is untyped JSON on the wire
 *  (`SourceOut.last_error`), not a generated enum, so this is keyed
 *  by the documented string values rather than a TypeScript union. */
const POLL_PROBLEM_HEADLINES: Record<string, string> = {
  source_error: "Couldn't reach the source",
  internal_error: "An unexpected error interrupted the poll",
  projects_incomplete:
    "The project list could not be fully read; some projects may be missing",
  listing_failed: "Couldn't list the files in this project",
  listing_incomplete:
    "The file list could not be fully read; some files may be missing",
  fetch_failed: "Couldn't fetch a changed file",
  ownership_conflict: "Skipped — already handled by an earlier registration",
  not_pollable: "This registration can't be polled",
};

/**
 * Plain-language headline for a poll-problem code (docs/ui-review
 * R-10, Task 8). The backend's own message, which is kept alongside
 * it as secondary "Details" text by the caller, carries the
 * per-instance specifics (which project, which file, the underlying
 * source error).
 *
 * :param code: The stable code from one `problems[]` entry, if any.
 * :returns: The headline, or `null` for a missing/unrecognised code
 *     (the caller falls back to the raw message alone).
 */
export function pollProblemLabel(code: string | undefined): string | null {
  if (code === undefined) {
    return null;
  }
  return POLL_PROBLEM_HEADLINES[code] ?? null;
}

/**
 * Plain-language headline for every stable source configuration
 * error code (`SourceOut.config_error_code`; docs/ui-review R-10).
 * The backend's own `config_error` text is kept alongside it by the
 * caller as secondary "Details" text: it carries the per-instance
 * specifics (which field, which env var name), which are never
 * parsed out of free text here. Shown to operators only, like the
 * rest of the problem detail (decision 3, Task 8).
 */
const CONFIG_ERROR_HEADLINES: Record<ConfigErrorCode, string> = {
  invalid_settings:
    "This registration's settings in catalog.yaml are not valid",
  unknown_type: "This registration uses a source type the catalog doesn't know",
  type_unavailable: "This source type isn't available in this build yet",
  invalid_published_ref: "The published branch setting is not valid",
  token_env_missing: "The access token's environment variable is not set",
  removed_from_config: "This registration was removed from catalog.yaml",
  other: "This registration's configuration has a problem",
};

/**
 * Plain-language headline for a source configuration error code.
 *
 * :param code: The stable code, or `null` when the backend sent none.
 * :returns: The headline, or `null` for `null`/an unrecognised code
 *     (the caller then shows the raw `config_error` text alone).
 */
export function configErrorLabel(code: ConfigErrorCode | null): string | null {
  if (code === null) {
    return null;
  }
  return CONFIG_ERROR_HEADLINES[code] ?? null;
}

/**
 * Per-config-error-code next step for an operator (Batch B/A4
 * follow-up to R-10): the generic per-source-type sentence this
 * replaced ("check the token env var, base_url, and scope...") was
 * wrong for codes that have nothing to do with it -- most sharply
 * `removed_from_config`, where there is no catalog.yaml entry left to
 * check at all, and `invalid_published_ref`, where the token is fine
 * but the ref setting is not.
 */
const CONFIG_ERROR_HINTS: Record<ConfigErrorCode, string> = {
  invalid_settings:
    "Fix this registration's settings in catalog.yaml, then restart " +
    "the backend.",
  unknown_type:
    "Set this registration's type to one the backend supports " +
    "(filesystem or gitlab) in catalog.yaml, then restart the backend.",
  type_unavailable:
    "Deploy a backend build that supports this source type, or change " +
    "the registration's type in catalog.yaml, then restart the backend.",
  invalid_published_ref:
    "Fix this registration's published_ref in catalog.yaml, then " +
    "restart the backend.",
  token_env_missing:
    "Set the access token's environment variable, then restart the " +
    "backend.",
  removed_from_config:
    "This registration is no longer in catalog.yaml. Restore it " +
    "there if it should keep polling; otherwise, no action is needed.",
  other:
    "Check this registration's settings in catalog.yaml, then restart " +
    "the backend.",
};

/**
 * Per-poll-problem-code next step for an operator, keyed the same way
 * as {@link pollProblemLabel}. `null` means the code describes an
 * outcome rather than something to fix (`not_pollable`: there is
 * nothing wrong with the registration, it simply cannot be polled).
 */
const POLL_PROBLEM_HINTS: Record<string, string | null> = {
  source_error:
    "Check connectivity to the source and the credentials or path in " +
    "catalog.yaml, then poll again.",
  internal_error: "Check the backend logs, then poll again.",
  projects_incomplete:
    "Poll again; if it keeps happening, check the source's rate " +
    "limits or permissions.",
  listing_failed:
    "Check the path and permissions for this project in catalog.yaml, " +
    "then poll again.",
  listing_incomplete:
    "Poll again; if it keeps happening, check the source's rate " +
    "limits or permissions.",
  fetch_failed:
    "Poll again; if it keeps failing, check whether the file still " +
    "exists at that path and ref.",
  ownership_conflict:
    "Remove the overlapping scope from one of the registrations in " +
    "catalog.yaml.",
  not_pollable: null,
};

/** Fallback next step when no stable code names a more specific one
 *  (an unrecognised code, or a `text`-kind problem with no code at
 *  all) -- the sentence this whole function replaces as the default,
 *  kept only as a last resort. */
const GENERIC_SOURCE_TYPE_HINTS: Record<string, string> = {
  gitlab:
    "Check the token env var, base_url, and scope in catalog.yaml, " +
    "then poll again.",
  filesystem:
    "Check the root path and scope in catalog.yaml, then poll again.",
};

/**
 * A concrete next step for the operator, tailored to the specific
 * problem rather than one generic per-source-type sentence
 * (docs/ui-review R-10; Batch B/A4 follow-up). Codes that carry no
 * useful specific advice (an unrecognised code, a `text`-kind problem
 * with none at all) fall back to the source type, same as before.
 *
 * :param problem: The row's problem display.
 * :param sourceType: The registration's source type (`"gitlab"`,
 *     `"filesystem"`), used only as the last-resort fallback.
 * :returns: A next step, or `null` when there is nothing to
 *     recommend (a healthy row, or `not_pollable`).
 */
export function recoveryHint(
  problem: SourceProblemDisplay,
  sourceType: string,
): string | null {
  if (problem.kind === "config") {
    return CONFIG_ERROR_HINTS[problem.code ?? "other"] ??
      GENERIC_SOURCE_TYPE_HINTS[sourceType] ?? null;
  }
  if (problem.kind === "list") {
    for (const item of problem.items) {
      const hint = POLL_PROBLEM_HINTS[item.code ?? ""];
      if (hint !== undefined) {
        return hint;
      }
    }
    return GENERIC_SOURCE_TYPE_HINTS[sourceType] ?? null;
  }
  if (problem.kind === "text") {
    return GENERIC_SOURCE_TYPE_HINTS[sourceType] ?? null;
  }
  return null;
}
