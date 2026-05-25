export async function registerPwaServiceWorker(): Promise<ServiceWorkerRegistration | null> {
  if (!("serviceWorker" in navigator)) {
    return null;
  }

  try {
    return await navigator.serviceWorker.register("/service-worker.js");
  } catch (error) {
    console.warn("PWA service worker registration failed", error);
    return null;
  }
}
