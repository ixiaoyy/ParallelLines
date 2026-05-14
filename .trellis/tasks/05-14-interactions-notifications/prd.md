# PRD: Interactions and Notifications

## Goal

Add community feedback loops: likes, bookmarks, board/topic follows, read state, and realtime notifications.

## Scope

- Backend models: `reactions`, `bookmarks`, `notifications`, subscriptions/read state extensions.
- Notification types: `replied`, `mentioned`, `liked`, `topic_new_post`, `board_new_topic`, `moderation`.
- APIs for like/unlike, bookmark/unbookmark, follow/unfollow, notification list/read state.
- SSE or WebSocket notification stream.
- Frontend optimistic updates for likes/bookmarks/follows.
- Notification bell and notification center.

## Acceptance Criteria

- Duplicate likes/bookmarks are impossible by database constraint and service logic.
- Notification records are created for replies and mentions.
- User can mark notifications as read.
- Realtime stream updates unread count without full page refresh.
- Read state shows which topics have unread replies.
