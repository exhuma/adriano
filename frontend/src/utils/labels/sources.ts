/**
 * Source/registration view-model helpers: the poll-status chip, its
 * secondary staleness text, and plain-language headlines for poll
 * problems and source configuration errors (operator-only detail;
 * decision 3, Task 8). Split from the former `utils/labels.ts` by
 * domain (module-code-structure-limits); see `index.ts`.
 */
import type { ConfigErrorCode, PollStatus } from "@/types/sources";

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
