# Frontend Quality Guidelines

## Required Checks

- `pnpm lint`
- `pnpm typecheck`
- `pnpm test` for unit/component tests when configured
- Playwright smoke tests for core flows after they exist

## Default Roadmap Testing Scope

- During normal development of roadmap tasks, default to downgraded testing: run frontend lint,
  typecheck, and only a focused browser/manual smoke for the touched UI path.
- Do not add or run broad per-task component/e2e matrices by default; final product-level
  verification will cover the full integrated experience after larger changes settle.
- Escalate to detailed frontend tests only when the user explicitly requests detailed/full testing,
  when preparing a commit/release, or when the change is high-risk (auth/security,
  destructive data actions, or large routing/state rewrites).

## UX Quality Bar

- Responsive layouts must work at mobile, tablet, and desktop widths.
- Skeleton/empty/error states are required for all async lists.
- Forms must show validation errors close to fields.
- New topic/reply flows must protect unsaved drafts.
- Long topic pages must avoid rendering thousands of posts at once.
- User-facing product copy defaults to Simplified Chinese (`zh-CN`). English is allowed only for product names, API identifiers, code examples, package names, and widely used technical terms such as FastAPI/OpenAPI/Vue.
- Navigation, empty states, badges, helper text, fixture topics, and seed community content must read like a Chinese technical forum rather than an English site with partial translation.

## Visual Quality Bar

- Use the requested palette exactly for core tokens.
- Code blocks use `#1E1E1E` background and readable syntax colors.
- Primary action hierarchy: blue for default action, green for success/online/accepted states.
- Keep card radius, border, and shadow consistent.

## Anti-patterns

- No inaccessible custom selects/modals without keyboard support.
- No layout shifts caused by unloaded avatars or counters.
- No unbounded polling when SSE/WebSocket is available.
