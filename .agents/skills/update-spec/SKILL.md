---
name: update-spec
description: "Update Trellis code-specs with concrete contracts, decisions, validations, cases, tests, and gotchas learned from work."
---

# Update Spec

Use when implementation/debugging/design reveals durable knowledge.

## Decide target

- How to implement safely -> `.trellis/spec/backend` or `frontend`
- What to think about/check -> `.trellis/spec/guides`
- New navigation -> update relevant `index.md`

## Required depth for infra/cross-layer changes

Specs must be executable, not principle-only. Include:

1. Scope / trigger
2. Signatures: command/API/function/DB paths
3. Contracts: request/response/env fields
4. Validation & error matrix
5. Good/base/bad cases
6. Tests required with assertion points
7. Wrong vs correct example when useful

## Process

1. State the learning/decision and why it matters.
2. Read the target spec before editing.
3. Add the smallest durable section:
   - design decision
   - convention
   - pattern
   - forbidden pattern
   - common mistake/gotcha
4. Avoid duplicating existing sections.
5. Update index if a new section/doc should be discoverable.

## Quality check

- concrete paths/names/fields included
- explains why
- testable
- in the right spec layer
- concise enough for future context loading
