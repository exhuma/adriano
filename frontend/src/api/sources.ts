/**
 * Typed calls to the source registration status and poll-trigger
 * API.
 */
import { api } from "@/api";
import type { SourceOut } from "@/types/sources";
import type { PollAcceptedOut } from "@/types/auth";

export type { SourceOut, PollAcceptedOut };

/**
 * List every stored source registration with its freshness.
 *
 * :returns: One entry per registration, ordered by id.
 */
export function listSources(): Promise<SourceOut[]> {
  return api.get<SourceOut[]>("/api/v1/sources");
}

/**
 * Trigger a background poll of every pollable registration.
 * Requires the `operate` permission.
 *
 * :returns: The accepted registration ids (HTTP 202); the outcome is
 *     visible shortly after on `GET /api/v1/sources`.
 * :throws ApiError: `403` without `operate`; `409` if nothing is
 *     pollable.
 */
export function pollAllSources(): Promise<PollAcceptedOut> {
  return api.post<PollAcceptedOut>("/api/v1/sources/poll");
}

/**
 * Trigger a background poll of one registration. Requires the
 * `operate` permission.
 *
 * :param id: Registration id.
 * :returns: The accepted id (HTTP 202).
 * :throws ApiError: `403` without `operate`; `404` for an unknown
 *     id; `409` if it cannot be polled (disabled or push-only).
 */
export function pollSource(id: string): Promise<PollAcceptedOut> {
  return api.post<PollAcceptedOut>(
    `/api/v1/sources/${encodeURIComponent(id)}/poll`,
  );
}
