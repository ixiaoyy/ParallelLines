# Frontend Development Guidelines

> Frontend stack for 平行线（internal package/project name: ParallelLines）: Vue 3, Vite, TypeScript, Ant Design Vue, Vue Router, Pinia, TanStack Query for Vue, generated OpenAPI client, SCSS, and CSS variables/design tokens.

## Overview

The frontend is a responsive forum interface with a calm tech aesthetic: `#F5F9FB` app background, `#005AA8` primary actions, `#08C7D8` cyan accent, `#172633` titles, `#314A5C` body text, and `#1E1E1E` code blocks.

## Guidelines Index

| Guide | Description | Status |
|-------|-------------|--------|
| [Directory Structure](./directory-structure.md) | Module organization and file layout | Filled |
| [Component Guidelines](./component-guidelines.md) | Component patterns, props, composition | Filled |
| [Forum API Wiring](./forum-api-wiring.md) | Board/topic/post DTO-to-VM mappings and query composables | Filled |
| [Board Visibility and Invites](./board-visibility-invites.md) | Invite-only board grouping, invite center, and private-board UI contracts | Filled |
| [Uploads, Avatars, and Attachments](./uploads-attachments.md) | Composer upload insertion, avatar upload, FormData API wiring, and asset URL resolution | Filled |
| [Hook Guidelines](./hook-guidelines.md) | Composables and data fetching patterns | Filled |
| [State Management](./state-management.md) | Local state, global state, server state | Filled |
| [Notifications and Interactions](./notifications-interactions.md) | Notification center, SSE, optimistic likes/bookmarks/follows | Filled |
| [Moderation Admin and Safety](./moderation-admin-safety.md) | Report actions, moderation queue UI, audit console, user status admin form | Filled |
| [Quality Guidelines](./quality-guidelines.md) | Code standards, forbidden patterns | Filled |
| [Smoke Tests](./smoke-tests.md) | Playwright MVP smoke flow and environment contract | Filled |
| [Post Actions](./post-actions.md) | Topic detail and post action button behavior | Filled |
| [Auth and User Session](./auth-user-session.md) | Login/register UI, verified session state, profile DTOs, and draft persistence | Filled |
| [Account Security UI](./account-security.md) | Forgot-password, 2FA login, security settings, sessions, and OAuth provider discovery UI contracts | Filled |
| [Topic Lifecycle UI](./topic-lifecycle.md) | Moderator toolbar, lifecycle mutations, cache invalidation, and closed-topic composer behavior | Filled |
| [Type Safety](./type-safety.md) | Type patterns, validation | Filled |

## Mandatory Pre-Development Checklist

1. Read `directory-structure.md` before adding files.
2. Read `component-guidelines.md` before building UI.
3. Read `forum-api-wiring.md` before changing board/topic/post API calls or DTO mappings.
4. Read `board-visibility-invites.md` before changing invite-only board grouping, invite center, or private-board UI.
5. Read `uploads-attachments.md` before changing composer uploads, avatar upload, or API-relative asset URLs.
6. Read `state-management.md` before adding state.
7. Read `type-safety.md` before defining API/domain types.
8. Read `notifications-interactions.md` before changing notification UI, SSE, likes, bookmarks, or follows.
9. Read `moderation-admin-safety.md` before changing report actions or the moderation console.
10. Read `smoke-tests.md` before changing Playwright smoke flows.
11. Read `post-actions.md` before changing topic detail or post action buttons.
12. Read `auth-user-session.md` before changing auth UI, current-user state, profile pages, or authenticated drafts.
13. Read `account-security.md` before changing forgot-password, 2FA login, security settings, or session revocation UI.
14. Read `topic-lifecycle.md` before changing close/open, pin, move, split, merge, or closed-topic composer behavior.
15. For cross-layer API work, read `../guides/cross-layer-thinking-guide.md`.

