/**
 * Typed calls to the not-indexed API: the documents intake could not
 * index. Every call goes through the shared `api` client (see
 * `@/api`); this module only builds paths and query strings. The list
 * is read-only -- entries clear on their own once the file is fixed
 * or removed, so there is no write call.
 */
import { api } from "@/api";
import { toQueryString } from "@/api/query";
import type {
  NotIndexedDetail,
  NotIndexedLocation,
  NotIndexedPage,
  NotIndexedParams,
} from "@/types/notIndexed";

/**
 * List the documents intake could not index, newest first.
 *
 * :param params: Optional source/project/reason/origin filters and
 *     pagination.
 * :returns: One page of entries.
 */
export function listNotIndexed(
  params: NotIndexedParams = {},
): Promise<NotIndexedPage> {
  return api.get<NotIndexedPage>(`/api/v1/not-indexed${toQueryString(params)}`);
}

/**
 * Fetch one entry with the content intake rejected.
 *
 * The location holds slashes (project, path, ref), so it travels as
 * four query parameters, not path segments.
 *
 * :param location: Registration, project, file path and ref.
 * :returns: The entry; `content` is `null` when it could not be read.
 * :throws ApiError: With `status === 404` when the entry no longer
 *     exists (it may have cleared since the list was read).
 */
export function getNotIndexedEntry(
  location: NotIndexedLocation,
): Promise<NotIndexedDetail> {
  return api.get<NotIndexedDetail>(
    `/api/v1/not-indexed/entry${toQueryString(location)}`,
  );
}
