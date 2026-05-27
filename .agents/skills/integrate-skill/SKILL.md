---
name: integrate-skill
description: "Fold an external skill's durable patterns into .trellis/spec guidelines and template examples, not app code."
---

# Integrate Skill

Use to adapt an external skill into project guidelines.

## Principle

Write durable guidance, not one-off code:

- Guidelines -> `.trellis/spec/{frontend|backend}/...`
- Examples -> `.trellis/spec/{layer}/examples/skills/<skill-name>/*`
- Code/config examples use `.template` suffix.

## Steps

1. Locate and read the source skill (`SKILL.md`). Ask for path only if not discoverable.
2. Pick target:
   - UI/design/testing browser -> frontend
   - API/backend/infra -> backend
   - workflow-only -> `.trellis/` or guides
3. Extract only reusable content:
   - project-applicable rules
   - patterns/contracts
   - caveats
   - examples worth templating
4. Update the target spec and index if navigation changes.
5. Add examples under `examples/skills/<skill-name>/` when useful.

## Report

- source skill
- target spec paths
- rules added
- templates added
- compatibility caveats
