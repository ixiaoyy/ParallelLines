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
| [Uploads, Avatars, and Attachments](./uploads-attachments.md) | Safe local uploads, avatar updates, attachment references, storage config, and private-board ACL | Filled |
| [Account Recovery and Login Security](./account-security.md) | Password reset, email change, 2FA, session revocation, and OAuth provider discovery contracts | Filled |
| [Moderation Admin and Safety](./moderation-admin-safety.md) | Flags, moderation queue, soft hide/restore, user status, audit logs | Filled |
| [Spam Prevention and Rate Limits](./spam-prevention-rate-limits.md) | Write-path throttles, screened email/IP/URL rules, auto-silence actions, and admin rule management | Filled |
| [Post Revisions and Restore](./post-revisions-history.md) | Post edit history, version detail, moderator restore, and audit/search consistency | Filled |
| [Topic Lifecycle](./topic-lifecycle.md) | Moderator close/open, pin, move, split, and merge contracts with counters and audit logs | Filled |
| [Admin Site Settings](./admin-site-settings.md) | Admin-only site settings, user management, system panel, public settings, mail logs, and audit contracts | Filled |
| [Background Jobs](./background-jobs.md) | Unified async queue, worker runtime, scheduled maintenance, retries, dead letters, and admin queue logs | Filled |
| [Email Notifications and Digests](./email-notifications-digests.md) | Email preferences, notification emails, digest jobs, delivery webhooks, and inbound reply contract | Filled |
| [Backup, Restore, and Export](./backup-restore-export.md) | Admin backup artifacts, safe restore validation, personal export, site export, checksums, and worker contract | Filled |
| [User Content Operations](./user-content-operations.md) | Public user profiles, authored topics, and post edit permissions | Filled |
| [User Social Relationships and Private Messages](./user-social-relationships-pm.md) | Follow/ignore/block users, notification suppression, and participant-only private message topics | Filled |
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
7. Read `uploads-attachments.md` before changing upload endpoints, avatar URLs, attachment storage, or upload cleanup.
8. Read `account-security.md` before changing password reset, email change, 2FA, sessions, or OAuth provider discovery.
9. Read `moderation-admin-safety.md` before changing flags, audit logs, moderator permissions, or hidden content visibility.
10. Read `spam-prevention-rate-limits.md` before changing write-path throttles, screened rules, or automatic spam actions.
11. Read `deployment-observability.md` before changing Docker, CI, seed data, metrics, or worker startup.
12. Read `quality-guidelines.md` before opening a PR.
13. Read `user-content-operations.md` before changing public user profile, authored topic, or post edit endpoints.
14. Read `post-revisions-history.md` before changing post edit history or restore behavior.
15. Read `topic-lifecycle.md` before changing topic status, pinning, move, split, merge, topic counters, or merged-topic routing.
16. Read `admin-site-settings.md` before changing admin settings, user management, public site settings, or system dashboard APIs.
17. Read `background-jobs.md` before changing mail delivery, notification fan-out, scheduled maintenance, or worker deployment.
18. Read `email-notifications-digests.md` before changing email preferences, notification emails, digest jobs, or provider webhooks.
19. Read `backup-restore-export.md` before changing backup artifacts, restore validation, backup downloads, or data exports.
20. Read `user-social-relationships-pm.md` before changing user follows, ignores, blocks, or private messages.
21. For cross-layer features, read `../guides/cross-layer-thinking-guide.md`.
