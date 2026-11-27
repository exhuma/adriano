/**
 * Router locations of the not-indexed pages. A not-indexed entry has
 * no id: it is addressed by its location (registration, project,
 * file path and ref), and project, path and ref contain slashes, so
 * the entry page takes the four values as query parameters.
 */
import type { RouteLocationRaw } from "vue-router";

import type { NotIndexedLocation } from "@/types/notIndexed";

/**
 * Location of the page showing one entry and its rejected content.
 *
 * :param location: Registration, project, file path and ref.
 * :returns: The router location.
 */
export function notIndexedEntryLocation(
  location: NotIndexedLocation,
): RouteLocationRaw {
  return {
    path: "/not-indexed/entry",
    query: {
      source_id: location.source_id,
      project: location.project,
      path: location.path,
      ref: location.ref,
    },
  };
}

/**
 * Location of the not-indexed list, optionally for one registration.
 *
 * :param sourceId: Registration id to filter by, if any.
 * :returns: The router location.
 */
export function notIndexedListLocation(sourceId?: string): RouteLocationRaw {
  return {
    path: "/not-indexed",
    query: sourceId ? { source: sourceId } : {},
  };
}
