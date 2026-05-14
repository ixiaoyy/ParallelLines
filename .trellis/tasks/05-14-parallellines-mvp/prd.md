# PRD: 平行线 MVP Project Blueprint

## Goal

Build 平行线, a Discourse-inspired forum product using Vue 3 and FastAPI. The product must support boards, topics, posts/replies, tags, search, follows, notifications, and basic moderation, with the requested calm tech color palette.

## Reference Inputs

- Product reference: https://meta.discourse.org/
- Source reference: `D:\work\discourse`
- Design document: `.trellis/spec/product/discourse-inspired-parallellines-design.md`
- Task plan: `.trellis/spec/product/trellis-task-plan.md`

## MVP Outcomes

1. A user can register/login, browse boards, follow a board, create a topic, reply, like, bookmark, and receive notifications.
2. A visitor can browse latest/hot/top topics and search public content.
3. A moderator can review reports and hide or restore content.
4. The frontend has a polished Vue 3 design system using the required palette.
5. The backend has typed FastAPI endpoints, migrations, tests, and generated OpenAPI.

## Child Tasks

- `05-14-architecture-domain-baseline`
- `05-14-backend-fastapi-foundation`
- `05-14-frontend-vue-design-system`
- `05-14-board-topic-post-core`
- `05-14-interactions-notifications`
- `05-14-search-feed-hot-ranking`
- `05-14-moderation-admin-safety`
- `05-14-quality-deployment-observability`

## Acceptance Criteria

- Trellis task tree is valid and each child has a PRD.
- Specs in `.trellis/spec/backend` and `.trellis/spec/frontend` are filled for the target stack.
- `.trellis/spec/product/discourse-inspired-parallellines-design.md` contains architecture, data model, API, UI, and milestones.
- `.trellis/spec/product/trellis-task-plan.md` contains dependency and parallelization guidance.
