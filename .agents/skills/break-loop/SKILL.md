---
name: break-loop
description: "Post-bug Trellis analysis: identify root cause, failed fixes, prevention, similar risks, and spec updates."
---

# Break Loop

Use after fixing a tricky or recurring bug.

## Analyze

1. Root cause category:
   - Missing spec
   - Cross-layer contract
   - Change propagation failure
   - Test coverage gap
   - Implicit assumption
2. Why earlier fixes failed, if any:
   - symptom-only fix
   - incomplete scope
   - tool/search limitation
   - wrong mental model
3. Prevention:
   - spec/docs
   - type/compile-time guard
   - runtime guard/monitoring
   - test coverage
   - review checklist
4. Systematic expansion:
   - similar code paths
   - architecture smell
   - process/spec gap
5. Capture knowledge:
   - update relevant `.trellis/spec/{backend,frontend,guides}` doc when useful

## Output

```markdown
## Bug Analysis: <name>
### Root Cause
### Failed Fixes
### Prevention
### Similar Risks
### Spec Updates
```

Do not leave valuable lessons only in chat. Do not commit unless explicitly asked.
