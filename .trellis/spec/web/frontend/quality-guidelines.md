# Quality Guidelines

## Validation by Change Type

Run checks once on the final state, proportional to the affected surface:

| Change | Minimum validation |
|---|---|
| Markdown/spec-only | `git diff --check` plus stale-template search |
| Vue/TypeScript/SCSS | `git diff --check` and `pnpm typecheck:web` |
| Broad frontend refactor | Add `pnpm lint:web`; use `pnpm build:web` when bundling or lazy imports change |
| API contract | Add `pnpm openapi:web:check` and the corresponding backend schema check |
| Critical user journey | Add a targeted Playwright test or run the relevant existing smoke file when services and fixtures are available |

The repository-level `AGENTS.md` is authoritative: do not run
`pnpm test:api` unless the user explicitly confirms the non-default test database
is ready.

## Review Requirements

- Inspect `git diff --check`, the scoped diff, and `git status` so unrelated user
  changes are not included.
- Exercise loading, error, empty, populated, disabled/pending, and permission
  states that the changed component owns.
- For responsive UI, check the content-driven breakpoint, 320px, a common
  390px phone viewport, and desktop. Verify no horizontal overflow and no fixed
  navigation covering content.
- Verify keyboard focus, accessible names, semantics, touch target size, and
  reduced-motion behavior.
- Search before changing a token, constant, query key, config value, route name,
  or shared type.
- Confirm API mutations invalidate every affected query family without clearing
  unrelated cache state.
- Remove diagnostic logs, temporary UI, dead selectors, and warning
  suppressions.

## Testing Style

Playwright smoke tests live under `apps/web/tests/smoke/`. They use accessible
locators (`getByRole`, `getByLabel`, and visible text) and assert real flows
against the running application. Follow `tests/smoke/mvp.spec.ts` for locator and
workflow style.

Prefer a focused regression test for changed behavior. Pure styling changes may
be verified by deterministic viewport screenshots and overflow assertions rather
than adding a low-value unit test.

### Browser Scroll Contract

`shared/styles/base.scss` sets `overflow-x: hidden` on both `html` and `body`.
In Chromium this makes `body` the vertical scrolling element for the current
application shell: `body.scrollHeight` grows with page content while
`document.documentElement.scrollHeight` may remain equal to the viewport.

Responsive tests that verify fixed-bottom-navigation clearance must scroll and
read the same container:

```ts
// Wrong: may remain at zero even when the page is scrollable.
window.scrollTo(0, document.documentElement.scrollHeight);
expect(window.scrollY).toBeGreaterThan(0);

// Correct for the current ParallelLines shell.
document.body.scrollTo(0, document.body.scrollHeight);
expect(document.body.scrollTop).toBeGreaterThan(0);
```

After scrolling, compare the final content rectangle with the fixed navigation's
top edge. `tests/smoke/admin-workbench-responsive.spec.ts` is the executable
reference. If the global overflow model changes, update this contract and the
test together.

## Forbidden Shortcuts

- Disabling strict TypeScript, ESLint rules, or accessibility behavior to make a
  check pass.
- Editing generated API types manually.
- Adding `any`, unchecked external-data assertions, or duplicated query keys.
- Replacing existing loading/error states with a success-only implementation.
- Running broad test suites repeatedly after the relevant targeted checks are
  already conclusive.
- Committing unrelated dirty files from another task or window.

## Handoff Checklist

- Acceptance criteria are mapped to inspected code or a validation result.
- Applicable specs still describe the final implementation.
- Protected brand assets and default paths are unchanged.
- The final response distinguishes checks that passed from checks not run because
  their required services or environment were unavailable.
