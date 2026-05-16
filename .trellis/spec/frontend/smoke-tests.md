# Frontend Smoke Test Contract

## Scenario: MVP browser smoke flow

### 1. Scope / Trigger

- Trigger: Playwright tests validating the end-to-end MVP path against a running API and web app.
- Applies to `apps/web/playwright.config.ts`, `apps/web/tests/smoke/`, and `package.json` `test:smoke` scripts.

### 2. Signatures

- Command: `pnpm --dir apps/web test:smoke`.
- Env:
  - `PLAYWRIGHT_BASE_URL` defaults to `http://127.0.0.1:5174`.
  - `PLAYWRIGHT_API_BASE_URL` defaults to `http://127.0.0.1:8000/api/v1`.

### 3. Contracts

- Smoke tests must use the browser UI for register, logout, and login once `/auth` exists.
- API setup may still bootstrap non-auth test data such as unique boards or secondary-user replies.
- Browser interactions must cover real frontend pages for publish, reply, profile, and post action flows.
- Test data must use unique usernames, emails, and board slugs per run.
- Tests should read the UI-created `parallellines.access_token` only for API bootstrap; do not inject auth state directly unless testing a legacy fallback.
- Smoke must include real-data regression checks after navigation/reload: a created board appears in board directory, a created topic appears in the home discovery stream, and created topic tags appear through the tag cloud/search surfaces.
- Assertions should scope duplicate accessible names to a landmark/region such as `主题发现流` or an explicit link label to avoid Playwright strict-mode ambiguity when the same real content is shown in multiple API-backed widgets.

### 4. Validation & Error Matrix

| Case | Expected behavior |
|---|---|
| API not reachable | Test fails before UI assertions with clear request failure |
| Web app built against wrong API | Publish/reply assertion fails, pointing to API URL mismatch |
| Existing seed data differs | Unique smoke board avoids collisions |
| UI auth succeeds | Topbar username link appears after register and login |
| Topic publish succeeds | Browser routes to topic detail and heading is visible |
| Reply succeeds | Reply body appears in the post stream |
| Only-author filter toggles | A secondary user's API-created reply becomes hidden, then visible again after "显示全部" |
| Real board directory data | API-created board is visible through `/boards` without fixture fallback |
| Real home discovery data | UI-created topic is visible on home after navigating away and back |
| Real tag data | UI-created tags are visible through API-backed tag UI |

### 5. Good/Base/Bad Cases

- Good: register/login through UI, create a unique board with the UI token, publish topic from `/new-topic`, reply from topic detail, then verify board/topic/tag visibility on API-backed pages.
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
