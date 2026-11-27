/**
 * Business-object types for the not-indexed list
 * (`GET /api/v1/not-indexed*`), derived from the generated OpenAPI
 * schema in `openapi.ts` (see `scripts/gen-types.mjs`).
 */
import type { components } from "@/types/openapi";

/** One document intake could not index, addressed by its location. */
export type NotIndexedItem = components["schemas"]["NotIndexedItemOut"];
/** One page of the not-indexed list. */
export type NotIndexedPage = components["schemas"]["NotIndexedPageOut"];
/** A not-indexed entry with the content intake rejected. */
export type NotIndexedDetail = components["schemas"]["NotIndexedDetailOut"];

/** Where a not-indexed entry is: registration, project, file, ref. */
export interface NotIndexedLocation {
  source_id: string;
  project: string;
  path: string;
  ref: string;
}

/** Query parameters accepted by `GET /api/v1/not-indexed`. */
export interface NotIndexedParams {
  /** Restrict to one registration id. */
  source_id?: string;
  /** Restrict to one project path. */
  project?: string;
  /** Restrict to entries carrying this reason (an issue code). */
  reason?: string;
  /** Restrict to entries found by `poll` or `push`. */
  origin?: "poll" | "push";
  /** 1-based page number. */
  page?: number;
  /** Page size, 1 to 50. */
  page_size?: number;
}
