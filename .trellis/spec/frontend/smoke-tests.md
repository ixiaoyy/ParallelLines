# Frontend Smoke Test Contract

## Scenario: Lightweight MVP browser smoke flow

### 1. Scope / Trigger

- Trigger: Playwright tests validating the shortest production-critical user path against a running API and web app.
- Applies to `apps/web/playwright.config.ts`, `apps/web/tests/smoke/`, and package `test:smoke` scripts.
- Default CI no longer runs Playwright smoke. Keep the lightweight command available for explicit local/manual validation; visual/performance checks, seeded persona checks, accessibility sweeps, and broad regression journeys belong to an explicit extended command.

### 2. Signatures

- Lightweight command: `pnpm --dir apps/web test:smoke`.
- Lightweight target: `apps/web/tests/smoke/mvp.spec.ts` only.
- Extended command: `pnpm --dir apps/web test:smoke:extended` for heavier/manual browser suites.
- Env:
  - `PLAYWRIGHT_BASE_URL` defaults to `http://127.0.0.1:5173`.
  - `PLAYWRIGHT_API_BASE_URL` defaults to `http://127.0.0.1:8000/api/v1`.

### 3. Contracts

- Default smoke uses the browser UI for register, email-code activation, logout, login, topic publish, and reply publish.
- API setup may bootstrap non-auth data such as a unique board needed for the publish flow.
- Test data must use unique usernames, emails, and board slugs per run.
- Smoke should read the UI-created `parallellines.access_token` only for API bootstrap; do not inject auth state directly in the default smoke path.
- Default smoke must not depend on fixed seeded usernames, fixed passwords, existing topics, existing replies, production data, visual snapshots, console-noise sweeps, or broad page-performance assertions.
- Heavier checks such as profile activity, notification center, only-author filtering, search result regressions, board/tag discovery, persona replies, and visual/performance audits should live in focused or extended Playwright suites.

### 4. Validation & Error Matrix

| Case | Expected behavior |
|---|---|
| API not reachable | Smoke fails before UI assertions with a clear request or navigation failure. |
| Web app built against wrong API | Register/publish/reply assertion fails, pointing to API URL mismatch. |
| Existing seed data differs | Lightweight smoke still passes because it creates unique auth and board/topic data. |
| UI auth succeeds | Topbar username link appears after register and login. |
| Topic publish succeeds | Browser routes to topic detail and heading is visible. |
| Reply succeeds | Reply body appears in the post stream. |

### 5. Good/Base/Bad Cases

- Good: register/login through UI, create a unique board with the UI token, publish a topic from `/new-topic`, reply from topic detail, and assert the visible topic/reply.
- Base: a developer or release operator starts MySQL, API, and Vite web server, installs Chromium, then runs `test:smoke` explicitly when a browser happy-path check is needed.
- Bad: default smoke depends on a fixed seeded username, a static board slug, existing topics, visual-performance checks, or long multi-page regression coverage.

### 6. Tests Required

- `pnpm --dir apps/web lint` must continue to pass with smoke files present.
- `pnpm --dir apps/web test:smoke -- --list` should list only the lightweight MVP smoke test.
- `pnpm --dir apps/web test:smoke` is optional/manual and should run only after API and web servers are healthy.
- `pnpm --dir apps/web test:smoke:extended` is optional/manual for heavier regression suites.

### 7. Wrong vs Correct

#### Wrong

```ts
const username = "oldhuai";
```

#### Correct

```ts
const suffix = Date.now().toString(36);
const username = `smoke_${suffix}`;
```
