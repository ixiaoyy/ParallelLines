---
name: finish-work
description: "Final Trellis handoff check: run affected validation, review specs/docs/tests, and list blockers before commit."
---

# Finish Work

Use when implementation is done and ready for human review/commit.

## Fast checklist

1. Inspect changes:
   ```bash
   git status --short
   git diff --name-only HEAD
   ```
2. Run affected validation:
   - Web: `pnpm lint:web`, `pnpm typecheck:web`, `pnpm --dir apps/web build` when UI/build changed
   - API: `pnpm lint:api`, `pnpm test:api`
   - OpenAPI: `pnpm openapi:api:check`, `pnpm openapi:web:check` when API contract changed
   - Smoke: `pnpm test:smoke` when user-facing web flows changed
3. Code quality scan:
   - no stray `console.log`
   - no new `any` / non-null assertion unless justified
   - no dead code or duplicated constants
4. Spec/doc sync:
   - update `.trellis/spec/backend` or `frontend` for new contracts/patterns
   - update guides only for thinking/checklist lessons
   - infra/cross-layer specs must include signatures, contracts, validation/errors, cases, tests
5. Manual/browser verification if UI changed.

## Output

```markdown
## Finish Work
- Changes:
- Validation:
- Spec/doc updates:
- Manual testing:
- Blockers:
```

Do not commit unless explicitly asked.
