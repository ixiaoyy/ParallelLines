---
name: check
description: "Verify changed code against relevant Trellis specs plus lint/type/test commands for affected frontend/backend areas."
---

# Check

Use after code changes or before handoff.

## Steps

1. Inspect changes:
   ```bash
   git diff --name-only HEAD
   git status --short
   ```
2. Pick relevant specs from changed paths:
   - `apps/web` -> `.trellis/spec/frontend/index.md`
   - `apps/api` -> `.trellis/spec/backend/index.md`
   - shared/API/schema -> also `.trellis/spec/guides/index.md`
3. Read only index checklist files relevant to the changes.
4. Run affected checks:
   ```bash
   pnpm lint:web
   pnpm typecheck:web
   pnpm lint:api
   pnpm test:api
   pnpm test:smoke
   ```
   Use only commands applicable to touched areas unless user asks for full validation.
5. Fix violations directly when safe.

## Output

- changed areas
- specs consulted
- checks run + pass/fail
- fixes made or remaining blockers
