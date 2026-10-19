/**
 * Backend status composable, backing the app bar's status indicator.
 *
 * Fetches `GET /healthz` once on creation and again whenever the
 * window regains focus, so a developer switching back to the tab
 * sees current backend availability without reloading.
 */
import { onMounted, onUnmounted, readonly, ref } from "vue";

import { api, ApiError } from "@/api";
import { withLoading } from "@/composables/useLoading";
import type { HealthPayload } from "@/types/health";

/** Outcome of the most recent health check. */
export type HealthCheckState = "checking" | "ok" | "degraded" | "error";

/** Narrow an unknown value down to a well-formed health payload. */
function isHealthPayload(value: unknown): value is HealthPayload {
  return (
    typeof value === "object" &&
    value !== null &&
    "status" in value &&
    "database" in value
  );
}

/** Reactive backend health status, refreshed on mount and on focus. */
export function useHealth() {
  const state = ref<HealthCheckState>("checking");
  const payload = ref<HealthPayload | null>(null);

  /** Re-fetch `/healthz` and update the reactive state. */
  async function check(): Promise<void> {
    state.value = "checking";
    try {
      const result = await withLoading(() =>
        api.get<HealthPayload>("/healthz"),
      );
      payload.value = result;
      state.value = result.status === "ok" ? "ok" : "degraded";
    } catch (error) {
      // The backend's 503 response is a well-formed HealthPayload
      // (status: "degraded"), not just a transport failure: show it
      // as "degraded" with its reported detail rather than a bare
      // "error" that would hide why the backend is unhealthy.
      if (error instanceof ApiError && isHealthPayload(error.data)) {
        payload.value = error.data;
        state.value = "degraded";
      } else {
        payload.value = null;
        state.value = "error";
      }
    }
  }

  function handleFocus(): void {
    void check();
  }

  onMounted(() => {
    void check();
    window.addEventListener("focus", handleFocus);
  });

  onUnmounted(() => {
    window.removeEventListener("focus", handleFocus);
  });

  return { state: readonly(state), payload: readonly(payload), check };
}
