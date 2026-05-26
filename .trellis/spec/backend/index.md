# Backend Development Guidelines

> Backend stack for 平行线（internal package/project name: ParallelLines）: FastAPI, Python 3.12+, SQLAlchemy 2.x async ORM, Alembic, MySQL/PostgreSQL, Redis, and background workers.

## Overview

The backend exposes a REST JSON API under `/api/v1`, generates OpenAPI from FastAPI/Pydantic, and keeps business transactions in service functions rather than routers. The domain model follows a Discourse-inspired split between boards/categories, topics, posts, user read state, actions, notifications, and moderation.

## Guidelines Index

| Guide | Description | Status |
|-------|-------------|--------|
| [Directory Structure](./directory-structure.md) | Module organization and file layout | Filled |
| [Database Guidelines](./database-guidelines.md) | ORM patterns, queries, migrations | Filled |
| [Error Handling](./error-handling.md) | Error types, handling strategies | Filled |
| [Interactions and Notifications](./interactions-notifications.md) | Likes, bookmarks, follows, notification fan-out contracts | Filled |
| [Search, Feed, and Hot Ranking](./search-feed-hot-ranking.md) | Search filters, public feeds, cursor meta, hot score recompute | Filled |
| [Board Visibility and Invites](./board-visibility-invites.md) | Private/invite-only board ACL, invitation lifecycle, and visibility-safe reads | Filled |
| [Board Management, Required Tags, and Defaults](./board-management-required-tags.md) | Child boards, scoped moderators, required/allowed tags, templates, and board defaults | Filled |
| [Uploads, Avatars, and Attachments](./uploads-attachments.md) | Safe local uploads, avatar updates, attachment references, storage config, and private-board ACL | Filled |
| [Account Recovery and Login Security](./account-security.md) | Password reset, email change, 2FA, session revocation, and OAuth provider discovery contracts | Filled |
| [Moderation Admin and Safety](./moderation-admin-safety.md) | Flags, moderation queue, soft hide/restore, user status, audit logs | Filled |
| [Spam Prevention and Rate Limits](./spam-prevention-rate-limits.md) | Write-path throttles, screened email/IP/URL rules, auto-silence actions, and admin rule management | Filled |
| [Post Revisions and Restore](./post-revisions-history.md) | Post edit history, version detail, moderator restore, and audit/search consistency | Filled |
| [Topic Lifecycle](./topic-lifecycle.md) | Moderator close/open, pin, move, split, and merge contracts with counters and audit logs | Filled |
| [Topic Solved, Voting, and Polls](./topic-solved-voting-polls.md) | Accepted answers, score voting, Q&A post ordering, and simple polls | Filled |
| [Admin Site Settings](./admin-site-settings.md) | Admin-only site settings, user management, system panel, public settings, mail logs, and audit contracts | Filled |
| [Background Jobs](./background-jobs.md) | Unified async queue, worker runtime, scheduled maintenance, retries, dead letters, and admin queue logs | Filled |
| [Email Notifications and Digests](./email-notifications-digests.md) | Email preferences, notification emails, digest jobs, delivery webhooks, and inbound reply contract | Filled |
| [Backup, Restore, and Export](./backup-restore-export.md) | Admin backup artifacts, safe restore validation, personal export, site export, checksums, and worker contract | Filled |
| [User Content Operations](./user-content-operations.md) | Public user profiles, authored topics, and post edit permissions | Filled |
| [User Profile Settings, Directory, and Activity](./user-profile-settings-directory.md) | Editable profile fields, privacy-aware public fields, user directory, and activity feed contracts | Filled |
| [User Social Relationships and Private Messages](./user-social-relationships-pm.md) | Follow/ignore/block users, notification suppression, and participant-only private message topics | Filled |
| [User Growth, Points, and Experience](./user-growth-points-experience.md) | Growth fields, reward rules, level calculation, ledger, and admin adjustments | Filled |
| [Badges and Trust Levels](./badges-trust-levels.md) | Badge catalog, user badge ledger, trust-level events, and risk-control contracts | Filled |
| [API Keys and Webhooks](./api-keys-webhooks.md) | Scoped API keys, outbound webhook events, HMAC signatures, retry jobs, and delivery logs | Filled |
| [Privacy, Retention, Anonymization, and Account Deletion](./privacy-data-retention-anonymization.md) | Personal exports, anonymized deletion, retention policy, and sensitive export/log redaction | Filled |
| [Public API, OpenAPI, and Compatibility](./public-api-openapi-client.md) | Stable OpenAPI snapshots, public docs, versioning/deprecation policy, and CI checks | Filled |
| [Plugin Extension System](./plugin-extension-system.md) | Safe plugin registry, admin enable/disable, backend event hooks, and public UI extension metadata | Filled |
| [Chat and Presence](./chat-presence.md) | Realtime chat channels, permissioned history, reconnect-safe SSE, and online/typing presence | Filled |
| [Analytics and Data Explorer](./analytics-data-explorer.md) | Admin analytics, preset reports, trend/top-list metrics, and audited CSV export | Filled |
| [Calendar Events](./calendar-events.md) | Community events, RSVP capacity/deadline, local timezone metadata, and iCal feed | Filled |
| [SEO, Permalinks, and Sitemap](./seo-permalinks-sitemap.md) | Public sitemap/robots, canonical metadata, legacy topic redirects, and private-content filtering | Filled |
| [Site Theme, Branding, and Text Overrides](./site-theme-i18n-branding.md) | Public/admin branding settings, theme color validation, i18n text overrides, and email templates | Filled |
| [External Integrations](./external-integrations.md) | GitHub/Zendesk/Patreon provider config, inbound webhooks, retryable events, and issue unfurling | Filled |
| [AI Forum Assistant](./ai-forum-assistant.md) | Deterministic topic summaries, similar-topic hints, and moderation advice guardrails | Filled |
| [Mobile Push and PWA](./mobile-push-pwa.md) | Web Push subscription storage and notification preference integration | Filled |
| [Import, Export, and Migration Tools](./import-export-migration-tools.md) | Admin JSON migration preview/run/export contracts and idempotency | Filled |
| [Localization and Multilingual Content](./localization-multilingual-content.md) | Locale validation, localizable topic/board fields, and fallback behavior | Filled |
| [Quality Guidelines](./quality-guidelines.md) | Code standards, forbidden patterns | Filled |
| [Logging Guidelines](./logging-guidelines.md) | Structured logging, log levels | Filled |
| [Deployment and Observability](./deployment-observability.md) | Docker Compose, CI, seed data, metrics, workers, smoke-test contracts | Filled |

## Mandatory Pre-Development Checklist

1. Read `directory-structure.md` before creating files.
2. Read `database-guidelines.md` before adding models or queries.
3. Read `error-handling.md` before adding endpoints.
4. Read `interactions-notifications.md` before changing likes, bookmarks, follows, or notifications.
5. Read `search-feed-hot-ranking.md` before changing topic feeds, search, or hot ranking jobs.
6. Read `board-visibility-invites.md` before changing board visibility, invites, board membership, or public read privacy.
6a. Read `board-management-required-tags.md` before changing child boards, board member roles, required/allowed tags, post templates, or board defaults.
7. Read `uploads-attachments.md` before changing upload endpoints, avatar URLs, attachment storage, or upload cleanup.
8. Read `account-security.md` before changing password reset, email change, 2FA, sessions, or OAuth provider discovery.
9. Read `moderation-admin-safety.md` before changing flags, audit logs, moderator permissions, or hidden content visibility.
10. Read `spam-prevention-rate-limits.md` before changing write-path throttles, screened rules, or automatic spam actions.
11. Read `deployment-observability.md` before changing Docker, CI, seed data, metrics, or worker startup.
12. Read `quality-guidelines.md` before opening a PR.
13. Read `user-content-operations.md` before changing public user profile, authored topic, or post edit endpoints.
14. Read `user-profile-settings-directory.md` before changing editable profile fields, privacy controls, user directory, or activity endpoints.
15. Read `post-revisions-history.md` before changing post edit history or restore behavior.
16. Read `topic-lifecycle.md` before changing topic status, pinning, move, split, merge, topic counters, or merged-topic routing.
17. Read `admin-site-settings.md` before changing admin settings, user management, public site settings, or system dashboard APIs.
18. Read `background-jobs.md` before changing mail delivery, notification fan-out, scheduled maintenance, or worker deployment.
19. Read `email-notifications-digests.md` before changing email preferences, notification emails, digest jobs, or provider webhooks.
20. Read `backup-restore-export.md` before changing backup artifacts, restore validation, backup downloads, or data exports.
21. Read `user-social-relationships-pm.md` before changing user follows, ignores, blocks, or private messages.
22. Read `topic-solved-voting-polls.md` before changing accepted answers, score votes, Q&A sorting, or polls.
23. Read `user-growth-points-experience.md` before changing points, experience, level rules, or growth rewards.
24. Read `badges-trust-levels.md` before changing badges, trust levels, or trust-adjusted risk controls.
25. Read `api-keys-webhooks.md` before changing API keys, integration scopes, webhook events, signatures, or delivery retries.
26. Read `privacy-data-retention-anonymization.md` before changing user exports, anonymization, account deletion, retention policy, or sensitive redaction.
27. Read `public-api-openapi-client.md` before changing OpenAPI metadata/snapshots, generated client contracts, public API docs, versioning, or deprecation policy.
28. Read `plugin-extension-system.md` before changing plugin definitions, event hook emit points, admin plugin APIs, or public UI extension metadata.
29. Read `chat-presence.md` before changing chat channels, chat history, SSE streams, or presence.
30. Read `analytics-data-explorer.md` before changing admin analytics, Data Explorer preset reports, or CSV exports.
31. Read `calendar-events.md` before changing community events, RSVP rules, reminders, or iCal feeds.
32. Read `seo-permalinks-sitemap.md` before changing sitemap, robots, canonical metadata, or legacy public redirects.
33. Read `site-theme-i18n-branding.md` before changing public/admin branding settings, theme colors, text overrides, or email template keys.
34. Read `external-integrations.md` before changing external provider configs, inbound webhooks, retries, or unfurling.
35. Read `ai-forum-assistant.md` before changing summaries, similar-topic recommendations, or moderation advice.
36. Read `mobile-push-pwa.md` before changing push subscriptions or push delivery contracts.
37. Read `import-export-migration-tools.md` before changing migration import/export formats or idempotency.
38. Read `localization-multilingual-content.md` before changing locale validation or localizable content fields.
39. For cross-layer features, read `../guides/cross-layer-thinking-guide.md`.
