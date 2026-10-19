/**
 * Typed calls to the source registration status API.
 */
import { api } from "@/api";
import type { SourceOut } from "@/types/sources";

export type { SourceOut };

/**
 * List every stored source registration with its freshness.
 *
 * :returns: One entry per registration, ordered by id.
 */
export function listSources(): Promise<SourceOut[]> {
  return api.get<SourceOut[]>("/api/v1/sources");
}
