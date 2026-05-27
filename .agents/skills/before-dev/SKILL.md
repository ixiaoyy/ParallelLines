---
name: before-dev
description: "Load only task-relevant Trellis specs before coding: package/layer index, checklist files, and triggered thinking guides."
---

# Before Dev

Use only for real, non-trivial code edits. Do not run this for every request.

## Skip

Skip before-dev for:

- questions, explanations, repo inspection, planning-only discussion
- skill/Trellis workflow edits under `.agents/`, `.codex/`, `.trellis/`
- typo/comment/copy changes with obvious local scope
- running diagnostics where no source code will be changed

## Tiers

### Lite

For localized code edits in known files:

1. Inspect target files first.
2. Read at most one relevant spec file if the change touches a known domain.
3. Skip package discovery if paths already identify the layer.

### Full

Use full before-dev only for new files, cross-layer/API/schema/infra changes, or unclear scope:

1. Discover layers only if paths are unknown:
   ```bash
   python ./.trellis/scripts/get_context.py --mode packages
   ```
2. Decide affected layer:
   - `apps/web` -> frontend
   - `apps/api` -> backend
   - both/API contract -> fullstack
3. Read only the relevant index:
   ```bash
   cat .trellis/spec/frontend/index.md
   cat .trellis/spec/backend/index.md
   ```
4. From that index, read only checklist files matching the task.
5. Read `.trellis/spec/guides/index.md`; open specific guides only when triggered:
   - cross-layer data flow/API/schema changes
   - repeated constants/patterns/new utilities

## Output

Report:

- specs read
- tier used or skipped
- patterns/constraints found
- files likely to modify

Never load both frontend and backend specs unless the task truly spans both.
