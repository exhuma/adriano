/**
 * Pure (Vue- and Vuetify-free) model of the search page's active
 * filter modes. Per the quartermaster `module-vue-vuetify` "mode indicators"
 * rules, the decision of *which* filter modes are active, their
 * fixed display order, and their full "what's in effect" text lives
 * here with no framework import, so it can be unit-tested without
 * mounting anything; `SearchView.vue` only renders whatever this
 * module hands it, as closable `v-chip`s inside a
 * `role="status" aria-live="polite"` region.
 *
 * The free-text query (`q`) is deliberately not one of these filter
 * modes: the search field itself is always visible and already shows
 * the active query continuously (module-ux-principles `ui-modes`:
 * "show it continuously while active"), so a redundant "Search:
 * ⟨text⟩" chip would restate, not add, information. `sort` is not a
 * filter mode either (it reorders, rather than narrows, the result
 * set) and gets no chip.
 */
import type { RecordState, RecordTypeFilter } from "@/types/records";

/** Identifies one filterable mode, in no particular order. */
export type FilterKey =
  | "needsApproval"
  | "source"
  | "project"
  | "state"
  | "recordType";

/** Current value of every filterable mode (the state filter's
 *  button-toggle value, or `""` for "all"). */
export interface ActiveFilterInput {
  needsApproval: boolean;
  source: string;
  project: string;
  state: RecordState | "";
  recordType: RecordTypeFilter;
}

/** One active filter mode, rendered as a closable chip. */
export interface ActiveFilterChip {
  /** Which filter this chip clears when closed. */
  key: FilterKey;
  /** Full "what's in effect" text (module-ux-principles `ui-modes`:
   *  state what is in effect, not just that something is active). */
  label: string;
  /** Material Design Icons name. */
  icon: string;
  /**
   * Vuetify theme colour token, always `primary` (coordinator browser
   * check: this app's light-theme `secondary`, #5CBBF6, is a chip
   * *fill* colour choice, not a *text* colour -- as the text/icon
   * colour on a `variant="tonal"` chip, where it is rendered at full
   * opacity over the pale 12% tint rather than composited the way a
   * solid fill would be, it is only about 2:1 against white, well
   * under WCAG's 4.5:1). `plugins/vuetify.ts` only verifies the
   * *theme* colours actually used this way (`primary`, `error`,
   * `warning`, `info`, `success`) for that exact text-on-tonal-tint
   * pairing (see `tests/plugins/vuetify.test.ts`); reusing `secondary`
   * here would need the same verification added for a colour nothing
   * else in the app renders as text, for no distinguishing benefit --
   * every chip already differs by icon and label text, so one colour
   * for every filter chip loses no information. `error`/`warning`
   * stay reserved for issues and rejection (decision 2).
   */
  color: "primary";
}

/** Fixed display order of filter modes (module-vue-vuetify
 *  "mode indicators": "one shared, ordered treatment"), matching the
 *  order the filter bar presents them in. */
const ORDER: readonly FilterKey[] = [
  "needsApproval",
  "source",
  "project",
  "state",
  "recordType",
];

function stateChipLabel(state: RecordState | ""): string | null {
  if (state === "published") {
    return "State: Published";
  }
  if (state === "candidate") {
    return "State: Candidate";
  }
  return null;
}

function recordTypeChipLabel(recordType: RecordTypeFilter): string | null {
  if (recordType === "erratum") {
    return "Show: Errata";
  }
  if (recordType === "all") {
    return "Show: Decisions and errata";
  }
  return null;
}

function buildChip(
  key: FilterKey,
  input: ActiveFilterInput,
): ActiveFilterChip | null {
  switch (key) {
    case "needsApproval":
      return input.needsApproval
        ? {
            key,
            label: "Needs approval",
            icon: "mdi-clipboard-alert-outline",
            color: "primary",
          }
        : null;
    case "source":
      return input.source
        ? {
            key,
            label: `Source: ${input.source}`,
            icon: "mdi-database-outline",
            color: "primary",
          }
        : null;
    case "project":
      return input.project
        ? {
            key,
            label: `Project: ${input.project}`,
            icon: "mdi-folder-outline",
            color: "primary",
          }
        : null;
    case "state": {
      const label = stateChipLabel(input.state);
      return label
        ? { key, label, icon: "mdi-file-clock-outline", color: "primary" }
        : null;
    }
    case "recordType": {
      const label = recordTypeChipLabel(input.recordType);
      return label
        ? {
            key,
            label,
            icon: "mdi-file-multiple-outline",
            color: "primary",
          }
        : null;
    }
    default:
      return null;
  }
}

/**
 * Compute the active-filter chips for the current filter values, in
 * their fixed display order.
 *
 * :param input: Current value of every filterable mode.
 * :returns: One chip per active mode, in display order; empty when
 *     no filter mode is active.
 */
export function activeFilterChips(
  input: ActiveFilterInput,
): ActiveFilterChip[] {
  const chips: ActiveFilterChip[] = [];
  for (const key of ORDER) {
    const chip = buildChip(key, input);
    if (chip) {
      chips.push(chip);
    }
  }
  return chips;
}
