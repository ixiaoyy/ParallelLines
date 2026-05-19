# Discourse-inspired Visitor Polish

## Goal
As a first-time visitor, compare ParallelLines against https://meta.discourse.org/ using Playwright screenshots, identify brutal-but-actionable UX gaps, and improve the project until a production-readiness maturity score reaches 90+.

## Requirements
- Capture baseline screenshots for local ParallelLines and Discourse Meta.
- Experience the site as a visitor and logged-in demo user where needed for core flows.
- Complete 10 iterative optimization rounds focused on visitor trust, information scent, density, navigation, responsive polish, empty/error states, and production feel.
- Keep changes frontend-scoped unless a blocker is discovered.
- Preserve Simplified Chinese product copy and project design tokens.

## Acceptance Criteria
- [ ] Playwright screenshots exist for before/after and Discourse reference.
- [ ] 10 optimization rounds are documented with before/after maturity scoring.
- [ ] Final maturity score is 90+.
- [ ] `pnpm --dir apps/web lint`, `typecheck`, and `build` pass.
- [ ] Playwright smoke flow passes against a local API/web pair.
- [ ] No production page uses fake fallback data.

## Technical Notes
- Use local SQLite smoke DB to avoid Docker dependency.
- Compare against Discourse patterns: instantly scannable topic rows, strong side navigation, crisp header, status density, category/tag affordance, and confident whitespace.
