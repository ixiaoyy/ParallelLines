# Frontend Quality Guidelines

## Required Checks

- `pnpm lint`
- `pnpm typecheck`
- `pnpm test` for unit/component tests when configured
- Playwright smoke tests for core flows after they exist

## UX Quality Bar

- Responsive layouts must work at mobile, tablet, and desktop widths.
- Skeleton/empty/error states are required for all async lists.
- Forms must show validation errors close to fields.
- New topic/reply flows must protect unsaved drafts.
- Long topic pages must avoid rendering thousands of posts at once.

## Visual Quality Bar

- Use the requested palette exactly for core tokens.
- Code blocks use `#1E1E1E` background and readable syntax colors.
- Primary action hierarchy: blue for default action, green for success/online/accepted states.
- Keep card radius, border, and shadow consistent.

## Anti-patterns

- No inaccessible custom selects/modals without keyboard support.
- No layout shifts caused by unloaded avatars or counters.
- No unbounded polling when SSE/WebSocket is available.
