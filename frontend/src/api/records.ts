/**
 * Typed calls to the records/facets read API. Every call goes
 * through the shared `api` client (see `@/api`), which owns
 * authentication headers and error shaping; this module only builds
 * paths and query strings.
 */
import { api } from "@/api";
import type {
  RecordDetail,
  SearchItem,
  SearchPage,
  SearchParams,
} from "@/types/records";
import type { FacetsOut } from "@/types/sources";

export type { SearchItem, SearchPage, SearchParams, RecordDetail };

/** Build a query string from a params object, dropping empty values. */
function toQueryString(params: SearchParams): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") {
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
 * :param params: Free text, source/project/state filters, and
 *     pagination.
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
