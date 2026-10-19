/**
 * Global page-loading state (module-vue-vuetify "State management" +
 * "Loading feedback").
 *
 * A module-level singleton so any view or composable can mark a
 * page-level fetch in flight and have the app bar's
 * `v-progress-linear` react, without a global state library. Uses a
 * counter so overlapping requests do not clear the indicator early.
 */
import { computed, ref } from "vue";

const activeRequests = ref(0);

/** Whether at least one tracked page-level request is in flight. */
export const isLoading = computed(() => activeRequests.value > 0);

/**
 * Run an async operation while the global loading indicator is
 * shown, decrementing the counter even if the operation throws.
 *
 * :param operation: Async function to run.
 * :returns: Whatever `operation` resolves to.
 */
export async function withLoading<T>(operation: () => Promise<T>): Promise<T> {
  activeRequests.value += 1;
  try {
    return await operation();
  } finally {
    activeRequests.value -= 1;
  }
}

/** Composable accessor for the global loading state. */
export function useLoading() {
  return { isLoading };
}
