# Mobile Push and PWA Frontend Contract

## Scope / Trigger

Applies when changing manifest, service worker, offline page, or push subscription UI.

## Contracts

- PWA assets live in `public/manifest.webmanifest`, `public/service-worker.js`, and `public/offline.html`.
- Service worker must provide navigation fallback to offline page and handle `push` / `notificationclick` safely.
- `PushNotificationPanel` lives on email preferences because push follows notification preference context.
- If `VITE_WEB_PUSH_PUBLIC_KEY` is absent, UI may send a local notification test but must not call subscription API.
- Subscription API payload contains endpoint plus `keys.p256dh/auth`; never log or render raw keys.

## Validation

Downgraded roadmap scope: frontend `typecheck` + `lint`; focused browser smoke only when a local app target is already running.
