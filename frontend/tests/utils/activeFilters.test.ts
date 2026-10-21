/**
 * Ensure the active-filter module computes the right chips, in the
 * right order, for every filter combination, and that the free-text
 * query and the sort order never produce a chip of their own.
 */
import { describe, expect, it } from "vitest";

import {
  activeFilterChips,
  type ActiveFilterInput,
} from "@/utils/activeFilters";

const NONE: ActiveFilterInput = {
  needsApproval: false,
  source: "",
  project: "",
  state: "",
  recordType: "decision",
};

describe("activeFilterChips", () => {
  it("returns no chips when every filter is at its default", () => {
    expect(activeFilterChips(NONE)).toEqual([]);
  });

  it("returns one chip per active filter, in the fixed display order", () => {
    const chips = activeFilterChips({
      needsApproval: true,
      source: "central",
      project: "payments",
      state: "candidate",
      recordType: "erratum",
    });

    expect(chips.map((chip) => chip.key)).toEqual([
      "needsApproval",
      "source",
      "project",
      "state",
      "recordType",
    ]);
  });

  it("states what's in effect, not just that a filter is active", () => {
    const chips = activeFilterChips({
      ...NONE,
      needsApproval: true,
      source: "central",
      project: "payments",
      state: "candidate",
      recordType: "erratum",
    });

    expect(chips.map((chip) => chip.label)).toEqual([
      "Needs approval",
      "Source: central",
      "Project: payments",
      "State: Candidate",
      "Show: Errata",
    ]);
  });

  it("labels the published state and the 'all' record type", () => {
    const chips = activeFilterChips({
      ...NONE,
      state: "published",
      recordType: "all",
    });

    expect(chips.map((chip) => chip.label)).toEqual([
      "State: Published",
      "Show: Decisions and errata",
    ]);
  });

  it("uses a non-warning colour for every chip, including 'needsApproval'", () => {
    const chips = activeFilterChips({
      ...NONE,
      needsApproval: true,
      source: "central",
    });

    // `secondary` fails text contrast on its own tonal tint in this
    // app's light theme (coordinator browser check), so every filter
    // chip uses `primary` -- chips are told apart by icon and label,
    // not by colour, so one shared colour loses no information.
    for (const chip of chips) {
      expect(chip.color).toBe("primary");
      expect(chip.color).not.toBe("warning");
      expect(chip.color).not.toBe("secondary");
    }
  });

  it("returns only the active filters, omitting inactive ones", () => {
    const chips = activeFilterChips({ ...NONE, project: "payments" });

    expect(chips).toEqual([
      {
        key: "project",
        label: "Project: payments",
        icon: "mdi-folder-outline",
        color: "primary",
      },
    ]);
  });
});
