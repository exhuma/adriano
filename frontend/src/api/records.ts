/**
 * Typed calls to the records/facets read API. Every call goes
 * through the shared `api` client (see `@/api`), which owns
 * authentication headers and error shaping; this module only builds
 * paths and query strings.
 */
import { api } from "@/api";
import type { RecordDiffOut } from "@/types/approval";
import type {
  RecordDetail,
  SearchItem,
  SearchPage,
  SearchParams,
} from "@/types/records";
import type { FacetsOut } from "@/types/sources";

export type { RecordDetail, SearchItem, SearchPage, SearchParams };

/** Build a query string from a params object, dropping empty/false
 *  values so the URL stays minimal. */
function toQueryString<T extends object>(params: T): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params as Record<string, unknown>)) {
    if (value === undefined || value === null || value === "" || value === false) {
      continue;
    }
    search.set(key, String(value));
  }
  const text = search.toString();
  return text.length > 0 ? `?${text}` : "";
}

/**
 * Search the catalog with the phase 1 filters.
 *
 * :param params: Free text, source/project/state/record-type filters,
 *     result order (`sort`; omitted for the server default -- see
 *     `SearchParams.sort`), and pagination. `toQueryString` drops
 *     `sort` from the request whenever it is `undefined`, exactly
 *     like every other optional filter.
 * :returns: The matching page of results.
 */
export function searchRecords(params: SearchParams): Promise<SearchPage> {
  return api.get<SearchPage>(`/api/v1/records${toQueryString(params)}`);
}

/**
 * Fetch one record's detail page.
 *
 * :param id: Record id (surrogate UUID, not the authored `adr_uuid`).
 * :returns: The detail payload.
 * :throws ApiError: With `status === 404` when the record does not
 *     exist.
 */
export function getRecord(id: string): Promise<RecordDetail> {
  return api.get<RecordDetail>(`/api/v1/records/${encodeURIComponent(id)}`);
}

/**
 * List sources and their projects, for the filter selects.
 *
 * :returns: The facets payload.
 */
export function getFacets(): Promise<FacetsOut> {
  return api.get<FacetsOut>("/api/v1/facets");
}

/** Digests to diff; omitted sides fall back to the server default. */
export interface DiffParams {
  /** Base digest (query `from`); default: last decided, else previous. */
  from?: string;
  /** Target digest (query `to`); default: the current digest. */
  to?: string;
}

/**
 * Diff two stored snapshots of a record's identity.
 *
 * :param id: Record id.
 * :param params: Optional base/target digests; only digests related
 *     to the record are accepted (404 `unknown_revision` otherwise).
 * :returns: The diff payload.
 */
export function getRecordDiff(
  id: string,
  params: DiffParams = {},
): Promise<RecordDiffOut> {
  const query = toQueryString({ from: params.from, to: params.to });
  return api.get<RecordDiffOut>(
    `/api/v1/records/${encodeURIComponent(id)}/diff${query}`,
  );
}
