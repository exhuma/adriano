/**
 * Pure view-model helpers mapping backend enum values to an
 * icon + text pair, so status is never shown by colour alone
 * (module-ux-principles "Do not rely on color alone"). Every
 * function here is a pure mapping with no I/O, reused by both
 * `SearchView`/`RecordView`/`SourcesView` and their tests.
 *
 * Split by domain into sibling modules
 * (module-code-structure-limits: the single `labels.ts` file grew
 * past the 500-line module limit) -- `approval.ts`, `records.ts`,
 * `errata.ts`, `search.ts`, `sources.ts`, `issues.ts`, with shared
 * types/constants in `shared.ts`. This file re-exports every public
 * symbol so existing `@/utils/labels` imports keep working unchanged.
 */

export type { StatusLabel } from "./shared";

export {
  approvalDisplayLabel,
  approvalStateExplanation,
  approvalStateLabel,
  decideBlockedLabel,
  decisionActionLabel,
  divergenceLabel,
} from "./approval";

export {
  displayStatusLabel,
  linkTypeLabel,
  recordKindTypeLabel,
  recordStateLabel,
} from "./records";

export {
  errataHeaderLinkText,
  errataHeadingText,
  erratumStatusLabel,
  erratumTypeLabel,
  pluralizeErrata,
} from "./errata";

export {
  candidateBranchText,
  searchApprovalStateLabel,
  searchErratumStatusLabel,
  searchRecordStateLabel,
} from "./search";

export {
  configErrorLabel,
  pollProblemLabel,
  pollStatusLabel,
  recoveryHint,
  staleStatusText,
} from "./sources";

export {
  issueCodeLabel,
  issueIndicatorLabel,
  validationIssueText,
} from "./issues";
