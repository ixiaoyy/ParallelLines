---
name: check-cross-layer
description: "Cross-layer safety check for API/schema/config/constant changes: trace data flow, reuse, imports, and consistency."
---

# Cross-Layer Check

Use after changes spanning 3+ layers, API/schema contracts, shared constants/configs, batch edits, or new utilities.

## Steps

1. Scope:
   ```bash
   git diff --name-only HEAD
   ```
2. Run only triggered dimensions:

### A. Data flow
Required for frontend/API/service/database changes.
- Trace read path: DB/service -> API -> UI.
- Trace write path: UI -> API -> service -> DB.
- Verify types, schemas, errors, loading states.

### B. Reuse/constants
Required for constants/config/hardcoded values.
```bash
grep -R "value-or-concept" apps .trellis -n
```
- Update all sites or extract shared constant.
- Search before creating helpers.

### C. Imports/dependencies
Required for new files/moves.
- Validate import style, no circular deps, correct layer ownership.

### D. Same-layer consistency
Required for display/format/domain logic.
- Search same concept in same layer.
- Align labels, colors, formatting, permissions, errors.

## Output

Report dimensions checked, evidence, issues fixed, and remaining risks.
