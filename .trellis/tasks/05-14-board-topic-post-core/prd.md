# PRD: Board Topic Post Core

## Goal

Deliver the first full user content loop: browse boards, create a topic, read it, and reply.

## Backend Scope

- Models/migrations: `boards`, `board_members`, `topics`, `posts`, `tags`, `topic_tags`, `topic_reads`.
- Services for creating board, creating topic with first post, replying, editing, soft deletion.
- APIs for board list/detail, topic list/detail, post stream, create/edit actions.
- Markdown render and sanitization pipeline.

## Frontend Scope

- Home latest/hot fixture-to-real data transition.
- Board page with topic filters.
- Topic detail with post stream.
- Composer for new topic and reply.

## Acceptance Criteria

- A logged-in user can create a board, create a topic in it, and add replies.
- Topic counters and last activity update correctly.
- Topic detail shows first post and replies with stable floor numbers.
- Markdown code blocks use dark code block styling.
- Tests cover service transaction and at least one end-to-end happy path.

## Progress

- [x] Backend models, services, migrations, and API routes for boards/topics/posts.
- [x] Frontend board directory, board detail, topic detail, new-topic, and reply UI.
- [x] Frontend pages wired to backend read APIs with fixture fallback for early setup.
- [x] New topic and reply flows wired to authenticated backend mutations while preserving drafts on failure.
