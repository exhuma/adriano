/**
 * Global test-environment polyfills that Vuetify components need
 * under jsdom, which implements neither `ResizeObserver` nor a real
 * `matchMedia`. Runs once before every test file (see
 * `vitest.config.ts` `test.setupFiles`).
 */

class ResizeObserverStub {
  /** No-op: layout observation is irrelevant under jsdom. */
  observe(): void {}
  /** No-op: layout observation is irrelevant under jsdom. */
  unobserve(): void {}
  /** No-op: layout observation is irrelevant under jsdom. */
  disconnect(): void {}
}

if (typeof globalThis.ResizeObserver === "undefined") {
  globalThis.ResizeObserver = ResizeObserverStub as unknown as typeof ResizeObserver;
}

// Vuetify's overlay positioning (`v-dialog`, `v-menu`, `v-snackbar`)
// reads `window.visualViewport`, which jsdom does not implement.
if (typeof window.visualViewport === "undefined") {
  window.visualViewport = {
    width: 1024,
    height: 768,
    addEventListener: () => {},
    removeEventListener: () => {},
  } as unknown as VisualViewport;
}

if (typeof window.matchMedia !== "function") {
  window.matchMedia = (query: string): MediaQueryList =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }) as unknown as MediaQueryList;
}
