# Frontend Smoke Test Contract

## Scenario: MVP browser smoke flow

### 1. Scope / Trigger

- Trigger: Playwright tests validating the end-to-end MVP path against a running API and web app.
- Applies to `apps/web/playwright.config.ts`, `apps/web/tests/smoke/`, and `package.json` `test:smoke` scripts.

### 2. Signatures

- Command: `pnpm --dir apps/web test:smoke`.
- Env:
  - `PLAYWRIGHT_BASE_URL` defaults to `http://127.0.0.1:5173`.
  - `PLAYWRIGHT_API_BASE_URL` defaults to `http://127.0.0.1:8000/api/v1`.

### 3. Contracts

- Smoke tests may use API setup for auth/bootstrap when the UI does not yet expose login.
- Browser interactions must still cover real frontend pages for publish and reply flows.
- Test data must use unique usernames, emails, and board slugs per run.
- Tests must set `parallellines.access_token` in local storage before using authenticated frontend writes.

### 4. Validation & Error Matrix

| Case | Expected behavior |
|---|---|
| API not reachable | Test fails before UI assertions with clear request failure |
| Web app built against wrong API | Publish/reply assertion fails, pointing to API URL mismatch |
| Existing seed data differs | Unique smoke board avoids collisions |
| Topic publish succeeds | Browser routes to topic detail and heading is visible |
| Reply succeeds | Reply body appears in the post stream |

### 5. Good/Base/Bad Cases

- Good: register and login via API, create a unique board, publish topic from `/new-topic`, reply from topic detail.
- Base: local developer runs Docker Compose, installs Chromium, runs `test:smoke`.
- Bad: smoke tests depend on a fixed seeded username or static board slug.

### 6. Tests Required

- `pnpm --dir apps/web lint` must continue to pass with smoke files present.
- `pnpm --dir apps/web test:smoke` should run in CI after API and web servers are healthy.

### 7. Wrong vs Correct

#### Wrong

```ts
const username = "smoke";
```

#### Correct

```ts
const suffix = Date.now().toString(36);
const username = `smoke_${suffix}`;
```
