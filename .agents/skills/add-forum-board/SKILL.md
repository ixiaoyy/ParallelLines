---
name: add-forum-board
description: "Add or update a ParallelLines forum board/category. Use when the user asks to add a new board, section, category, 版块, 栏目, or named content area such as sports/news/reading, including backend seed migrations and frontend board navigation/display constants."
---

# Add Forum Board

Use this workflow to add one durable forum board to ParallelLines.

## Steps

1. Confirm inputs:
   - Required: display name and intent.
   - Choose a short ASCII slug when missing; ask only if multiple reasonable slugs/names would change product meaning.
   - Default visibility is `public` unless the user explicitly asks for invite-only/private.
2. Gather evidence before editing:
   ```powershell
   rg -n "<slug>|<name>|related terms" apps .trellis/spec -g "!**/node_modules/**" -g "!**/dist/**"
   git status --short --branch
   ```
   Check the actual board/migration/frontend state; do not assume a slug is unused from memory.
3. Read only relevant specs:
   - `.trellis/spec/backend/database-guidelines.md`
   - `.trellis/spec/backend/board-visibility-invites.md`
   - `.trellis/spec/backend/board-management-required-tags.md`
   - `.trellis/spec/frontend/forum-api-wiring.md`
   - `.trellis/spec/frontend/board-visibility-invites.md`
   - `.trellis/spec/frontend/board-management-required-tags.md`
   - `.trellis/spec/guides/cross-layer-thinking-guide.md` for backend + frontend changes.
4. Implement backend data source:
   - Add an Alembic data migration after the current mainline head.
   - Create/update `boards.slug`, `name`, `description`, `color`, `visibility`, notification/default-sort fields.
   - Keep the migration idempotent, safe on missing tables, and no-op on an empty board table.
   - Preserve user content on downgrade; do not delete a board that may have topics.
   - If adding helper functions, include clear docstrings covering purpose, key parameters, return value, and side effects.
5. Implement display wiring:
   - Add the slug to `apps/api/app/services/forum.py` `BOARD_DISPLAY_ORDER` if the product order should be fixed.
   - Preserve the rule that `feedback` / 社区反馈 stays last; unknown public boards sort before it.
   - Update frontend recognition only where needed:
     - `apps/web/src/pages/board/BoardDirectoryPage.vue` for recommended boards, icon, and short purpose.
     - `apps/web/src/pages/home/components/HomeLeftRail.vue` for left-rail icon.
     - `apps/web/src/shared/theme/boardPalette.ts` for board tone.
     - `apps/web/src/pages/board/BoardPage.vue` only when a custom hero SVG is truly needed.
   - Do not change Logo/favicon assets or primary button/theme colors while adding a board.
6. Verify:
   ```powershell
   git diff --check
   python -m py_compile <new-migration.py> apps/api/app/services/forum.py
   pnpm typecheck:web
   pnpm lint:web
   ```
   Do not run `pnpm test:api` unless the user explicitly says the local test database is ready.
7. Final review:
   - Search the new slug/name again to confirm all intended locations were updated.
   - Compare against `origin/main` (or `origin/master` only if that ref exists).
   - Check newly added `def`/`function` blocks for required comments/docstrings.
   - Report changed files, validations, and any pre-existing unrelated dirty files.

## Output

- Board name and slug added.
- Backend migration path.
- Frontend display paths changed.
- Validation commands and results.
