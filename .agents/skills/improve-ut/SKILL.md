---
name: improve-ut
description: "Improve tests for changed code: choose unit/integration/regression scope, follow existing patterns, run targeted validation."
---

# Improve Unit Tests

Use after feature/bug changes or when coverage gaps are found.

## Steps

1. Inspect changed files:
   ```bash
   git diff --name-only HEAD
   ```
2. Read relevant test/spec guidance if present:
   ```bash
   python ./.trellis/scripts/get_context.py --mode packages
   ```
3. Find existing nearby tests and patterns.
4. Choose scope:
   - unit for pure logic
   - integration for API/service/db flow
   - regression for fixed bugs
5. Add/update tests with minimal fixtures/mocks.
6. Run affected checks: `pnpm test:api`, web test command, lint/typecheck as applicable.

## Output

- changed areas
- test scope
- tests added/updated
- validation result
- remaining gaps
