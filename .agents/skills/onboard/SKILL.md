---
name: onboard
description: "Onboard a developer to Trellis concepts, repo structure, core skills, examples, and guideline customization status."
---

# Onboard

Use for a new developer or someone learning the Trellis workflow.

## Cover briefly

1. Why Trellis exists:
   - AI sessions lack memory -> `.trellis/workspace`
   - AI needs project conventions -> `.trellis/spec`
   - AI drifts over long context -> `$check` / `$finish-work`
2. Structure:
   - `.trellis/workflow.md`
   - `.trellis/tasks/*/prd.md`
   - `.trellis/spec/{frontend,backend,guides}`
   - `.agents/skills/*`
3. Core skills:
   - `$start`: restore context
   - `$before-dev`: load relevant specs
   - `$brainstorm`: scope unclear work
   - `$check`: verify changes
   - `$finish-work`: final handoff
   - `$record-session`: persist completed work
4. Example flows:
   - bug fix: start -> before-dev -> fix -> check -> finish -> record
   - planning: start -> brainstorm/task -> record decisions
   - refactor: start -> plan phases -> check each phase -> finish
5. Guideline status:
   ```bash
   grep -R "To be filled by the team" .trellis/spec -n
   ```
   If placeholders exist, help fill them from real code patterns.

## Output

Keep it teachable but concise. End by asking what first task they want to do.
