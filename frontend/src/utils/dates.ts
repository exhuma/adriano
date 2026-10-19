/**
 * Date/time formatting with the platform `Intl` APIs only (no date
 * library dependency; module-vue-vuetify "Dependencies").
 */

const dateFormatter = new Intl.DateTimeFormat(undefined, { dateStyle: "long" });
const dateTimeFormatter = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
  timeStyle: "short",
});
const relativeFormatter = new Intl.RelativeTimeFormat(undefined, {
  numeric: "auto",
});

const UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["year", 1000 * 60 * 60 * 24 * 365],
  ["month", 1000 * 60 * 60 * 24 * 30],
  ["day", 1000 * 60 * 60 * 24],
  ["hour", 1000 * 60 * 60],
  ["minute", 1000 * 60],
  ["second", 1000],
];

/**
 * Format a `YYYY-MM-DD` decision date for display.
 *
 * :param value: ISO date string, or `null`/`undefined` when unset.
 * :returns: A long-form localized date, or `null` when unset.
 */
export function formatDate(value: string | null | undefined): string | null {
  if (!value) {
    return null;
  }
  // Parse as a calendar date (no timezone shift) by splitting the
  // ISO string rather than feeding it to `Date` directly.
  const [year, month, day] = value.split("-").map(Number);
  if (!year || !month || !day) {
    return value;
  }
  return dateFormatter.format(new Date(year, month - 1, day));
}

/**
 * Format an ISO timestamp as an absolute, localized date and time.
 *
 * :param value: ISO timestamp string, or `null`/`undefined` when
 *     unset.
 * :returns: A medium-form localized date-time, or `null` when unset.
 */
export function formatDateTime(value: string | null | undefined): string | null {
  if (!value) {
    return null;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return dateTimeFormatter.format(date);
}

/**
 * Format an ISO timestamp as a relative time ("3 hours ago").
 *
 * :param value: ISO timestamp string, or `null`/`undefined` when
 *     unset.
 * :param now: Reference time (overridable for tests).
 * :returns: A relative-time phrase, or `null` when unset.
 */
export function formatRelativeTime(
  value: string | null | undefined,
  now: Date = new Date(),
): string | null {
  if (!value) {
    return null;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  const diffMs = date.getTime() - now.getTime();
  for (const [unit, unitMs] of UNITS) {
    if (Math.abs(diffMs) >= unitMs || unit === "second") {
      return relativeFormatter.format(Math.round(diffMs / unitMs), unit);
    }
  }
  return relativeFormatter.format(0, "second");
}
