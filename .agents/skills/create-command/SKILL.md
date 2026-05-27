---
name: create-command
description: "Create a concise project skill under .agents/skills with frontmatter, triggerable description, and executable steps."
---

# Create Command / Skill

Create `.agents/skills/<skill-name>/SKILL.md`.

## Steps

1. Parse input:
   - skill name in kebab-case
   - purpose/trigger
2. Check existing skills for overlap:
   ```bash
   ls .agents/skills .codex/skills 2>/dev/null
   ```
3. Generate concise `SKILL.md`:
   ```markdown
   ---
   name: <skill-name>
   description: "<short trigger-rich description>"
   ---

   # <Title>

   When to use, steps, output format.
   ```
4. Keep body under ~100 lines unless the workflow truly needs more.
5. Confirm path and usage: `$<skill-name>`.

## Guidelines

- Description should include trigger nouns/actions.
- Prefer commands and checklists over long explanations.
- Do not duplicate an existing skill.
