# Frontend Development Guidelines

> Frontend stack for 平行线（internal package/project name: ParallelLines）: Vue 3, Vite, TypeScript, Ant Design Vue, Vue Router, Pinia, TanStack Query for Vue, generated OpenAPI client, SCSS, and CSS variables/design tokens.

## Overview

The frontend is a responsive forum interface with a calm tech aesthetic: `#F8FAFC` app background, `#409EFF` primary actions, `#10B981` success accent, `#334155` titles, `#475569` body text, and `#1E1E1E` code blocks.

## Guidelines Index

| Guide | Description | Status |
|-------|-------------|--------|
| [Directory Structure](./directory-structure.md) | Module organization and file layout | Filled |
| [Component Guidelines](./component-guidelines.md) | Component patterns, props, composition | Filled |
| [Forum API Wiring](./forum-api-wiring.md) | Board/topic/post DTO-to-VM mappings and query composables | Filled |
| [Board Visibility and Invites](./board-visibility-invites.md) | Invite-only board grouping, invite center, and private-board UI contracts | Filled |
| [Board Management, Required Tags, and Defaults](./board-management-required-tags.md) | Board hierarchy, settings panel, member roles, templates, and required tag guidance | Filled |
| [Uploads, Avatars, and Attachments](./uploads-attachments.md) | Composer upload insertion, avatar upload, FormData API wiring, and asset URL resolution | Filled |
| [Hook Guidelines](./hook-guidelines.md) | Composables and data fetching patterns | Filled |
| [State Management](./state-management.md) | Local state, global state, server state | Filled |
| [Notifications and Interactions](./notifications-interactions.md) | Notification center, SSE, optimistic likes/bookmarks/follows | Filled |
| [Moderation Admin and Safety](./moderation-admin-safety.md) | Report actions, moderation queue UI, audit console, user status admin form | Filled |
| [Quality Guidelines](./quality-guidelines.md) | Code standards, forbidden patterns | Filled |
| [Smoke Tests](./smoke-tests.md) | Playwright MVP smoke flow and environment contract | Filled |
| [Post Actions](./post-actions.md) | Topic detail and post action button behavior | Filled |
| [Auth and User Session](./auth-user-session.md) | Login/register UI, verified session state, profile DTOs, and draft persistence | Filled |
| [User Profile Settings, Directory, and Activity UI](./user-profile-settings-directory.md) | Editable profile form, member directory, privacy-aware activity tabs, and profile query invalidation | Filled |
| [Account Security UI](./account-security.md) | Forgot-password, 2FA login, security settings, sessions, and OAuth provider discovery UI contracts | Filled |
| [Topic Lifecycle UI](./topic-lifecycle.md) | Moderator toolbar, lifecycle mutations, cache invalidation, and closed-topic composer behavior | Filled |
| [Topic Solved, Voting, and Polls UI](./topic-solved-voting-polls.md) | Accepted answer controls, score voting, Q&A order, and poll voting UI contracts | Filled |
| [Admin Dashboard](./admin-dashboard.md) | Admin dashboard, site settings UI, public setting refresh, user management, system health, and audit/mail panels | Filled |
| [Email Preferences](./email-preferences.md) | User email notification toggles, digest frequency UI, API wiring, and authenticated navigation | Filled |
| [User Social Relationships and Private Messages](./user-social-relationships-pm.md) | Profile follow/ignore/block controls, private-message creation, and PM inbox | Filled |
| [Badges and Trust Levels UI](./badges-trust-levels.md) | Trust/badge DTOs, profile chips, topic/post author metadata, and admin badge controls | Filled |
| [API Keys and Webhooks UI](./api-keys-webhooks.md) | Admin integration panel, API key/webhook DTOs, one-time secret reveal, and delivery logs | Filled |
| [SEO, Permalinks, and Sitemap UI](./seo-permalinks-sitemap.md) | Browser canonical tags, OpenGraph/Twitter metadata, and SPA permalink behavior | Filled |
| [Rich Composer, Onebox, Emoji, and Code UX](./rich-composer-onebox-emoji.md) | Markdown toolbar, safe preview, drag/paste uploads, onebox cards, emoji, and code-block copy | Filled |
| [Site Theme, Branding, and i18n Text UI](./site-theme-i18n-branding.md) | Public branding application, top-level i18n fallbacks, and admin theme preview/rollback | Filled |
| [Public API, OpenAPI, and Generated Types UI](./public-api-openapi-client.md) | OpenAPI-generated DTO types, compile-time drift checks, and CI type generation | Filled |
| [Plugin Extension System UI](./plugin-extension-system.md) | Admin plugin toggles, public extension slots, generated plugin DTOs, and safe internal-link rendering | Filled |
| [Chat and Presence UI](./chat-presence.md) | Realtime chat page, SSE cache reconciliation, channel query keys, and safe message rendering | Filled |
| [Analytics and Data Explorer UI](./analytics-data-explorer.md) | Admin analytics panel, range-aware report queries, preset Data Explorer, and authenticated CSV export | Filled |
| [Calendar Events UI](./calendar-events.md) | Calendar page, local-time display, RSVP mutations, and iCal subscription link | Filled |
| [External Integrations UI](./external-integrations.md) | Admin provider config, redacted secrets, event retries, and GitHub issue previews | Filled |
| [AI Forum Assistant UI](./ai-forum-assistant.md) | Topic summaries, similar-topic hints, and advisory AI UX | Filled |
| [Theme Marketplace UI](./theme-marketplace.md) | Built-in theme packages, validation, preview, enable, and rollback | Filled |
| [Mobile Push and PWA UI](./mobile-push-pwa.md) | Manifest/service worker/offline page and Push subscription panel | Filled |
| [Import, Export, and Migration Tools UI](./import-export-migration-tools.md) | Admin JSON migration preview/run/export UX contracts | Filled |
| [Localization and Multilingual Content UI](./localization-multilingual-content.md) | App locale state, site text override fallback, and localized topic/board display | Filled |
| [Type Safety](./type-safety.md) | Type patterns, validation | Filled |

## Mandatory Pre-Development Checklist

1. Read `directory-structure.md` before adding files.
2. Read `component-guidelines.md` before building UI.
3. Read `forum-api-wiring.md` before changing board/topic/post API calls or DTO mappings.
4. Read `board-visibility-invites.md` before changing invite-only board grouping, invite center, or private-board UI.
4a. Read `board-management-required-tags.md` before changing board hierarchy, settings, member roles, templates, or required tags.
5. Read `uploads-attachments.md` before changing composer uploads, avatar upload, or API-relative asset URLs.
6. Read `state-management.md` before adding state.
7. Read `type-safety.md` before defining API/domain types.
8. Read `notifications-interactions.md` before changing notification UI, SSE, likes, bookmarks, or follows.
9. Read `moderation-admin-safety.md` before changing report actions or the moderation console.
10. Read `smoke-tests.md` before changing Playwright smoke flows.
11. Read `post-actions.md` before changing topic detail or post action buttons.
12. Read `auth-user-session.md` before changing auth UI, current-user state, profile pages, or authenticated drafts.
13. Read `user-profile-settings-directory.md` before changing editable profile forms, member directory, or profile activity UI.
14. Read `account-security.md` before changing forgot-password, 2FA login, security settings, or session revocation UI.
15. Read `topic-lifecycle.md` before changing close/open, pin, move, split, merge, or closed-topic composer behavior.
16. Read `admin-dashboard.md` before changing `/admin`, public site settings, user management, system health, or admin navigation.
17. Read `email-preferences.md` before changing `/email-preferences`, email preference API wiring, or mail navigation.
18. Read `user-social-relationships-pm.md` before changing profile relationship actions, PM creation, or `/messages`.
19. Read `topic-solved-voting-polls.md` before changing accepted answer controls, score voting, Q&A ordering, or polls.
20. Read `badges-trust-levels.md` before changing trust/badge profile, author metadata, or admin badge UI.
21. Read `api-keys-webhooks.md` before changing admin integration UI, API key/webhook DTOs, scopes/events, or delivery logs.
22. Read `seo-permalinks-sitemap.md` before changing canonical tags, share metadata, or topic/board/user permalink behavior.
23. Read `rich-composer-onebox-emoji.md` before changing composer toolbar, safe preview, drag/paste uploads, onebox cards, emoji, or code-block copy.
24. Read `site-theme-i18n-branding.md` before changing app shell branding, public text fallbacks, or admin theme preview/rollback.
25. Read `public-api-openapi-client.md` before changing generated OpenAPI types, frontend DTO contracts, or API drift checks.
26. Read `plugin-extension-system.md` before changing plugin slots, plugin admin UI, extension query keys, or plugin DTO helpers.
27. Read `chat-presence.md` before changing chat routes, SSE stream parsing, chat query keys, or presence UI.
28. Read `analytics-data-explorer.md` before changing admin analytics panels, range-aware report query keys, or CSV export UI.
29. Read `calendar-events.md` before changing event routes, RSVP UI, local time formatting, or calendar query keys.
30. Read `external-integrations.md` before changing admin external integration UI or GitHub issue preview wiring.
31. Read `ai-forum-assistant.md` before changing topic AI summary or similar-topic UX.
32. Read `theme-marketplace.md` before changing theme package validation or admin theme marketplace UI.
33. Read `mobile-push-pwa.md` before changing manifest, service worker, offline page, or push subscription UI.
34. Read `import-export-migration-tools.md` before changing admin migration preview/run/export UI.
35. Read `localization-multilingual-content.md` before changing locale switching, site text fallback, or localized content display.
36. For cross-layer API work, read `../guides/cross-layer-thinking-guide.md`.
