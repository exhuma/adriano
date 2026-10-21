/**
 * Business-object types for `GET /api/v1/sources` and
 * `GET /api/v1/facets`, derived from the generated OpenAPI schema in
 * `openapi.ts` (see `scripts/gen-types.mjs`).
 */
import type { components } from "@/types/openapi";

/** How content entered the catalog: poll or authenticated push. */
export type IntakeKind = components["schemas"]["IntakeKind"];
/** Stable reason why a registration's configuration is invalid. */
export type ConfigErrorCode = components["schemas"]["ConfigErrorCode"];
/** Outcome of the latest poll of a registration. */
export type PollStatus = components["schemas"]["PollStatus"];
/** One source registration's configuration and freshness. */
export type SourceOut = components["schemas"]["SourceOut"];
/** Record count of one project within a source. */
export type FacetProjectOut = components["schemas"]["FacetProjectOut"];
/** One source's projects, for the filter select. */
export type FacetSourceOut = components["schemas"]["FacetSourceOut"];
/** Filter options for the search UI. */
export type FacetsOut = components["schemas"]["FacetsOut"];
