/**
 * Business-object types for the records API (`/api/v1/records*`,
 * `/api/v1/facets`), derived from the generated OpenAPI schema in
 * `openapi.ts` (see `scripts/gen-types.mjs`). Components and
 * composables import from here, never from `openapi.ts` directly, so
 * the generated file can be regenerated without touching call sites.
 */
import type { components } from "@/types/openapi";

/** Lifecycle state of a stored record row: published or candidate. */
export type RecordState = components["schemas"]["RecordState"];
/** Kind of ADR record: a normal decision or an erratum. */
export type RecordKind = components["schemas"]["RecordKind"];
/** The six approval states of a record's current content. */
export type ApprovalStateCode = components["schemas"]["ApprovalStateCode"];
/** Formal decision recorded by a reviewer: accepted or rejected. */
export type DecisionAction = components["schemas"]["DecisionAction"];
/** Configuration status of the global approval policy. */
export type PolicyStatus = components["schemas"]["PolicyStatus"];
/** Display status derived from inbound lifecycle links. */
export type DisplayStatus = components["schemas"]["DisplayStatus"];
/** Reverse names of the `updates` / `obsoletes` links. */
export type InboundType = components["schemas"]["InboundType"];
/** Outbound relationship types, named as written in frontmatter. */
export type LinkType = components["schemas"]["LinkType"];
/** Tier at which an outbound link was resolved. */
export type Resolution = components["schemas"]["Resolution"];
/** Severity of a validation issue. */
export type Severity = components["schemas"]["Severity"];
/** Stable machine-readable validation issue code. */
export type IssueCode = components["schemas"]["IssueCode"];
/** Where a record's display title came from. */
export type TitleSource = components["schemas"]["TitleSource"];

/** One validation finding attached to a record. */
export type IssueOut = components["schemas"]["IssueOut"];
/** Stored-issue counts of one record, by severity. */
export type IssueCountsOut = components["schemas"]["IssueCountsOut"];
/** One search result row. */
export type SearchItem = components["schemas"]["SearchItemOut"];
/** One page of search results. */
export type SearchPage = components["schemas"]["SearchPageOut"];
/** Identity and authored metadata of one record. */
export type MetadataOut = components["schemas"]["MetadataOut"];
/** Where a record's content came from. */
export type ProvenanceOut = components["schemas"]["ProvenanceOut"];
/** Freshness of a record's owning registration. */
export type FreshnessOut = components["schemas"]["FreshnessOut"];
/** One outbound link and how it resolved. */
export type OutboundLinkOut = components["schemas"]["OutboundLinkOut"];
/** A link from another record to the one being viewed. */
export type InboundLinkOut = components["schemas"]["InboundLinkOut"];
/** One erratum record correcting the record being viewed. */
export type ErratumOut = components["schemas"]["ErratumOut"];
/** Counts of a record's errata for the top notice. */
export type ErrataSummaryOut = components["schemas"]["ErrataSummaryOut"];
/** The structured content of an erratum, shown on its own page. */
export type ErratumContentOut = components["schemas"]["ErratumContentOut"];
/** The decision an erratum corrects, resolved like outbound links. */
export type ErratumForOut = components["schemas"]["ErratumForOut"];
/** Kind of correction an erratum reports. */
export type ErratumType = components["schemas"]["ErratumType"];
/** One published or candidate row sharing a record's identity. */
export type SiblingOut = components["schemas"]["SiblingOut"];
/** The applicable approval policy, or why there is none. */
export type PolicySummaryOut = components["schemas"]["PolicySummaryOut"];
/** One historical decision event, read-only in phase 05. */
export type DecisionSummaryOut = components["schemas"]["DecisionSummaryOut"];
/** Approval state of a record's current content. */
export type ApprovalOut = components["schemas"]["ApprovalOut"];
/** Everything the record detail page shows. */
export type RecordDetail = components["schemas"]["RecordDetailOut"];
/** Search filter restricting results to decisions, errata, or both. */
export type RecordTypeFilter = components["schemas"]["RecordTypeFilter"];

/** Query parameters accepted by `GET /api/v1/records`. */
export interface SearchParams {
  /** Free text (titles, bodies, UUIDs, paths). */
  q?: string;
  /** Restrict to one registration id. */
  source?: string;
  /** Restrict to one project path. */
  project?: string;
  /** Restrict to `published` or `candidate`. */
  state?: RecordState;
  /** Restrict to records whose current content needs approval. */
  needs_approval?: boolean;
  /** Restrict to decisions (default), errata, or both. */
  record_type?: RecordTypeFilter;
  /** 1-based page number. */
  page?: number;
  /** Page size, 1 to 50. */
  page_size?: number;
}
