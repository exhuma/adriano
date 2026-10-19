/**
 * Business-object type for `GET /healthz` (module-vue-vuetify
 * "Business-object typing"). Mirrors the backend's
 * `app/routers/health.py` response shape.
 */

/** Overall application health status. */
export type HealthStatus = "ok" | "degraded";

/** Database connectivity status as reported by `/healthz`. */
export type DatabaseStatus = "ok" | "unavailable";

/** Catalog configuration file status, as loaded at startup. */
export type ConfigFileStatus = "ok" | "missing" | "invalid" | "unknown";

/** Approval policy configuration status, as loaded at startup. */
export type PolicyConfigStatus = "configured" | "missing" | "invalid" | "unknown";

/** Source registration sync status, as performed at startup. */
export type RegistrationsSyncStatus = "synced" | "skipped" | "failed" | "unknown";

/** Response body of `GET /healthz`. */
export interface HealthPayload {
  /** `"ok"` when the app and its dependencies are healthy. */
  status: HealthStatus;
  /** `"ok"` when the database is reachable. */
  database: DatabaseStatus;
  /** Status of the `catalog.yaml` file loaded at startup. */
  config?: ConfigFileStatus;
  /** Status of the configured global approval policy. */
  policy?: PolicyConfigStatus;
  /** Outcome of syncing source registrations at startup. */
  registrations?: RegistrationsSyncStatus;
}
