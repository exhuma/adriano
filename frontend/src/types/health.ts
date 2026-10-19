/**
 * Business-object type for `GET /healthz` (module-vue-vuetify
 * "Business-object typing"). Mirrors the backend's
 * `app/routers/health.py` response shape.
 */

/** Overall application health status. */
export type HealthStatus = "ok" | "degraded";

/** Database connectivity status as reported by `/healthz`. */
export type DatabaseStatus = "ok" | "unavailable";

/** Response body of `GET /healthz`. */
export interface HealthPayload {
  /** `"ok"` when the app and its dependencies are healthy. */
  status: HealthStatus;
  /** `"ok"` when the database is reachable. */
  database: DatabaseStatus;
}
