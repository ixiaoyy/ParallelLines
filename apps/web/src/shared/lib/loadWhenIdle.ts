/**
 * Waits until the browser has idle time before starting non-critical work.
 * Key parameter: `timeoutMs` is the maximum delay before continuing. Return value: resolves when work may start.
 * Side effect: schedules one browser idle callback or timeout; it does not mutate application state.
 */
export function runWhenBrowserIdle(timeoutMs = 1200): Promise<void> {
  if (typeof window === "undefined") {
    return Promise.resolve();
  }

  return new Promise((resolve) => {
    if ("requestIdleCallback" in window) {
      window.requestIdleCallback(() => resolve(), { timeout: timeoutMs });
      return;
    }

    globalThis.setTimeout(resolve, Math.min(timeoutMs, 300));
  });
}
