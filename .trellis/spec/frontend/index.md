# Frontend Development Guidelines

> Frontend stack for 平行线（internal package/project name: ParallelLines）: Vue 3, Vite, TypeScript, Ant Design Vue, Vue Router, Pinia, TanStack Query for Vue, generated OpenAPI client, SCSS, and CSS variables/design tokens.

## Overview

The frontend is a responsive forum interface with a calm tech aesthetic: `#F8F9FA` app background, `#3B82F6` primary actions, `#10B981` geek accent, `#111827` titles, `#4B5563` body text, and `#1E1E1E` code blocks.

## Guidelines Index

| Guide | Description | Status |
|-------|-------------|--------|
| [Directory Structure](./directory-structure.md) | Module organization and file layout | Filled |
| [Component Guidelines](./component-guidelines.md) | Component patterns, props, composition | Filled |
| [Forum API Wiring](./forum-api-wiring.md) | Board/topic/post DTO-to-VM mappings and query composables | Filled |
| [Hook Guidelines](./hook-guidelines.md) | Composables and data fetching patterns | Filled |
| [State Management](./state-management.md) | Local state, global state, server state | Filled |
| [Notifications and Interactions](./notifications-interactions.md) | Notification center, SSE, optimistic likes/bookmarks/follows | Filled |
| [Moderation Admin and Safety](./moderation-admin-safety.md) | Report actions, moderation queue UI, audit console, user status admin form | Filled |
| [Quality Guidelines](./quality-guidelines.md) | Code standards, forbidden patterns | Filled |
| [Smoke Tests](./smoke-tests.md) | Playwright MVP smoke flow and environment contract | Filled |
| [Type Safety](./type-safety.md) | Type patterns, validation | Filled |

## Mandatory Pre-Development Checklist

1. Read `directory-structure.md` before adding files.
2. Read `component-guidelines.md` before building UI.
3. Read `forum-api-wiring.md` before changing board/topic/post API calls or DTO mappings.
4. Read `state-management.md` before adding state.
5. Read `type-safety.md` before defining API/domain types.
6. Read `notifications-interactions.md` before changing notification UI, SSE, likes, bookmarks, or follows.
7. Read `moderation-admin-safety.md` before changing report actions or the moderation console.
8. Read `smoke-tests.md` before changing Playwright smoke flows.
9. For cross-layer API work, read `../guides/cross-layer-thinking-guide.md`.
