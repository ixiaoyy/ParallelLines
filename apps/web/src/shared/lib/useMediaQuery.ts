import { onMounted, onUnmounted, readonly, ref } from "vue";

// Tracks a CSS media query in Vue state so components can avoid mounting hidden desktop/mobile-only work.
// Key parameter: `query` is any valid media query string; `fallback` is used before browser APIs exist.
// Return value is a readonly boolean ref. Side effect: installs and removes one matchMedia listener on mount.
export function useMediaQuery(query: string, fallback = false) {
  const matches = ref(typeof window === "undefined" ? fallback : window.matchMedia(query).matches);
  let mediaQuery: MediaQueryList | null = null;

  // Syncs browser MediaQueryList changes into Vue state; side effect is updating the local `matches` ref.
  function syncMediaQuery(event: MediaQueryListEvent | MediaQueryList) {
    matches.value = event.matches;
  }

  onMounted(() => {
    mediaQuery = window.matchMedia(query);
    syncMediaQuery(mediaQuery);

    if (mediaQuery.addEventListener) {
      mediaQuery.addEventListener("change", syncMediaQuery);
      return;
    }

    mediaQuery.addListener(syncMediaQuery);
  });

  onUnmounted(() => {
    if (!mediaQuery) {
      return;
    }

    if (mediaQuery.removeEventListener) {
      mediaQuery.removeEventListener("change", syncMediaQuery);
      return;
    }

    mediaQuery.removeListener(syncMediaQuery);
  });

  return readonly(matches);
}
