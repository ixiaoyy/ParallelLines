---
name: brainstorm
description: "Scope unclear Trellis tasks: create/seed PRD, inspect repo first, propose options, ask one high-value question at a time."
---

# Brainstorm

Use for vague, multi-path, or architectural work. Optimize for fast convergence.

## Rules

- Create/ensure a task only for real work, not casual questions.
- Inspect repo/docs before asking questions.
- Ask one blocking/preference question at a time.
- Offer 2-3 concrete options with trade-offs for decisions.
- Keep `prd.md` current; do not let decisions live only in chat.

## Flow

1. Ensure task directory exists:
   ```bash
   TASK_DIR=$(python ./.trellis/scripts/task.py create "brainstorm: <goal>" --slug <slug>)
   ```
2. Seed `prd.md` with:
   - Goal
   - Known facts
   - Assumptions
   - Open Questions
   - Requirements
   - Acceptance Criteria
   - Out of Scope
   - Technical Notes
3. Auto-context before questions:
   - likely files/modules
   - similar patterns
   - relevant specs/indexes
   - constraints from configs/scripts
4. Classify depth:
   - trivial/simple -> stop brainstorming and implement
   - moderate -> 1-3 questions
   - complex -> options + explicit MVP boundary
5. Converge to a final summary:
   - Goal
   - Requirements
   - Acceptance Criteria
   - Out of Scope
   - Technical Approach
   - Implementation Plan

## Research-first triggers

Research/inspect first when choosing a library, architecture, protocol, CLI/API UX, or when the user asks for best practices.

## Handoff

After user approves scope, continue with normal task workflow: targeted specs -> context setup -> implement -> check.
