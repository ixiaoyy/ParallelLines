# brainstorm: Public and invite-only boards

## Goal

让首页左侧版块导航区明确区分「公共版块」与「邀请版块」。公共版块对所有访问者可见；邀请版块只能被受邀请/已加入该版块的用户看见，避免私密空间名称、入口和主题内容泄露。

## What I already know

* 用户提出：左侧的板块分为公共板块和邀请版块；邀请版块只有受邀请的人才能看见。
* 当前首页左侧 rail 在 `apps/web/src/pages/home/HomePage.vue` 中渲染，`railBoards = boardSummaries.slice(0, 8)`，目前未分组。
* 前端 `BoardResponse` 已接收 `visibility` 字段，但 `toBoardSummary` 会丢弃该字段，UI 无法按可见性分组。
* 后端 `Board.visibility` 已存在，当前字面量为 `public | private | unlisted`，但没有专门的 `invite_only` 命名。
* 后端已有 `board_members` 表，可表达用户是否属于版块，创建者会成为 `owner`。
* 当前 `GET /api/v1/boards`、`GET /api/v1/boards/{slug}`、`GET /api/v1/boards/{slug}/topics` 都不接收当前用户，也未按 `visibility`/`board_members` 做过滤；如果只做前端隐藏，不能满足「只有受邀请的人才能看见」。
* 当前 API client 会在存在 token 时自动带 Authorization header；但 FastAPI 依赖目前只有强制登录的 `CurrentUserDep`，没有 optional current user dependency。

## Assumptions (temporary)

* 「邀请版本」理解为「邀请版块」。
* 邀请版块应同时隐藏版块入口、主题列表、主题详情和搜索/全站 Feed 中的内容；否则仍会泄露私密内容。
* MVP 可以先复用 `board_members` 表作为“已被邀请/已加入”的授权依据，后续再补完整邀请链接、邀请码、待接受邀请等流程。

## Open Questions

* 公共版块由谁创建/管理？

## Requirements (evolving)

* 左侧版块导航展示两个清晰分组：公共版块、邀请版块。
* 游客/未受邀用户只能看到公共版块。
* 登录且是某邀请版块成员的用户，可以看到对应邀请版块入口。
* 邀请版块的名称、入口、主题列表、搜索结果和全站 Feed 不应泄露给未授权用户。
* 前端应使用 API 返回的权限过滤结果，而不是只在浏览器本地过滤。
* MVP 包含完整邀请流程，而不只是访问控制：按已注册用户名创建邀请、查看待处理邀请、接受邀请、拒绝邀请、撤回/失效邀请、成员可见性生效。
* 普通成员可以创建自己的版块，但只能创建邀请版块，不能创建公共版块。
* 普通成员创建版块时默认 `visibility` 为 invite-only/private；前端不向普通用户提供公共版块选项，后端也必须拒绝普通用户提交 public visibility。
* 邀请权限限定为版块 owner：用户只能邀请他人进入自己创建/拥有的版块；普通成员不能邀请他人进入非自己拥有的版块。
* 邀请入口采用已注册用户名；不在首版发送邮箱、不生成公开邀请链接。
* 邀请管理入口采用单独「我的邀请」页面，而不是只放在版块详情侧栏。
* 「我的邀请」页面至少包含两个区块：我收到的邀请（接受/拒绝）和我管理的邀请（仅展示自己拥有的版块；按用户名邀请、查看待处理、撤回）。
* 顶部导航或通知中心应能让登录用户进入「我的邀请」页面；邀请通知点击后进入该页面或对应邀请详情。
* 被邀请用户接受后成为该邀请版块成员，并出现在左侧「邀请版块」分组。
* 待接受邀请不应让未登录游客看到私密版块内容；只有邀请目标本人登录后可看到待处理邀请提示/入口。

## Acceptance Criteria (evolving)

* [ ] 首页左侧 rail 将版块分为「公共版块」与「邀请版块」。
* [ ] 未登录用户调用版块列表时只收到/看到公共版块。
* [ ] 已登录但未受邀用户看不到邀请版块，也不能通过 slug 直接访问其版块页或主题列表。
* [ ] 受邀/成员用户可以看到并进入自己的邀请版块。
* [ ] 登录用户可以从独立「我的邀请」页面处理收到的邀请。
* [ ] 普通成员可以创建自己拥有的邀请版块。
* [ ] 普通成员创建版块时即使提交 `visibility=public`，后端也拒绝或强制降级为邀请版块（待实现时选择其一并测试）。
* [ ] 版块 owner 可以在「我的邀请」页面按用户名发出邀请并看到自己拥有版块的待处理邀请列表。
* [ ] 非 owner 成员不能邀请他人进入不属于自己的版块。
* [ ] 邀请目标用户可以接受或拒绝邀请。
* [ ] 版块 owner / moderator 可以撤回待处理邀请或移除成员。
* [ ] 已接受、已拒绝、已撤回、已过期的邀请不能被重复接受。
* [ ] 全站 topic feed、搜索、用户内容列表等公共读取面不泄露无权限邀请版块内容。
* [ ] 后端权限边界有单元/集成测试覆盖 public 与 invite-only 的 Good/Base/Bad cases。
* [ ] 前端 smoke 或组件测试覆盖左侧分组展示与未授权隐藏。

## Definition of Done (team quality bar)

* Tests added/updated (unit/integration where appropriate)
* Lint / typecheck / CI green
* Docs/notes updated if behavior changes
* Rollout/rollback considered if risky

## Out of Scope (explicit)

* 邀请链接、邮箱发送、批量邀请、组织级权限、跨版块角色模板暂不纳入首版。
* 暂不改变版块关注通知等级语义，除非权限实现必须区分 follow 与 invite membership。
* 暂不做组织/团队级权限模型。

## Technical Notes

* Relevant UI: `apps/web/src/pages/home/HomePage.vue`, `apps/web/src/pages/home/HomePage.scss`。
* Board detail page already has a right sidebar in `apps/web/src/pages/board/BoardPage.vue`, but MVP UI decision is to use a standalone invites page instead. Board page may link to it later.
* Topbar already has `NotificationBell.vue`; invite notifications can reuse the existing notification center pattern if the API emits a `board_invite` notification type.
* Board VM/API mapping: `apps/web/src/entities/board/model.ts`, `apps/web/src/features/boards/model.ts`, `apps/web/src/features/boards/queries.ts`。
* Backend model/schema/service: `apps/api/app/models/forum.py`, `apps/api/app/schemas/forum.py`, `apps/api/app/services/forum.py`, `apps/api/app/api/v1/boards.py`。
* Current frontend appears to have no create-board UI; board creation exists via `POST /api/v1/boards` and smoke tests call the API directly. MVP needs a member-facing create-board entry/page or modal that only creates invite-only/private boards for regular users.
* Cross-layer concern: this changes API visibility contract and likely requires backend + frontend + tests.
* Relevant specs to read before implementation: `.trellis/spec/backend/database-guidelines.md`, `.trellis/spec/backend/error-handling.md`, `.trellis/spec/backend/search-feed-hot-ranking.md`, `.trellis/spec/frontend/forum-api-wiring.md`, `.trellis/spec/frontend/component-guidelines.md`, `.trellis/spec/guides/cross-layer-thinking-guide.md`。

## Research Notes

### Current repo constraints

* Existing `visibility` supports `public`, `private`, `unlisted`. Product wording can map「邀请版块」to `private` for MVP, or add an explicit `invite_only` enum if clearer.
* Existing `BoardMember` can serve as the authorization table. However, “关注版块” and “受邀可见” are currently overloaded if every follower is a member; MVP must define whether following a public board creates membership that grants private access, or whether private boards are only manually/invite-created members.
* Public endpoints currently assume all boards/topics are public; adding invite-only visibility requires filtering at query level, not merely UI conditionals.

### Feasible approaches here

**Approach A: Reuse `private` as invite-only visibility (Recommended MVP)**

* How it works: Treat `Board.visibility == "private"` as「邀请版块」; a board is visible when public, or when current user has `BoardMember` row for that board. Add optional auth dependency and filter board/topic queries.
* Pros: No migration needed for visibility enum/string; uses existing schema; fastest path to secure MVP.
* Cons: Product copy says invite-only while database says private; invite lifecycle remains implicit/manual.

**Approach B: Add explicit `invite_only` visibility**

* How it works: Extend allowed visibility to `public | invite_only | unlisted` or `public | private | invite_only | unlisted`, migrate/seed data, update API types and UI labels.
* Pros: Domain language matches product copy; future invite workflow clearer.
* Cons: Larger cross-layer change; requires migration/seed/test updates; need define relationship between `private` and `invite_only`.

**Approach C: Frontend-only grouping first**

* How it works: Keep API unchanged, expose `visibility` in `BoardSummary`, group left rail by visibility.
* Pros: Very quick visual iteration.
* Cons: Does not satisfy “只有受邀请的人才能看见”; private boards would still leak through API, direct URLs, feeds, search.

## Decision (ADR-lite)

**Context**: 用户明确选择完整邀请流程，而不是仅实现左侧分组或后端可见性过滤。

**Decision**: MVP 纳入邀请生命周期：按已注册用户名创建邀请、待处理邀请查看、接受/拒绝、撤回/失效、成员可见性生效，并把邀请版块访问控制落到后端查询边界。

**Consequences**: 任务从前端 polish 扩大为跨层功能，预计需要新增邀请模型/迁移、API schema/service/router、普通成员创建版块 UI、独立「我的邀请」页面、左侧分组 UI，以及后端和前端测试。

## UI Decision

* Route: add a logged-in-only `/invites` / `my-invites` page.
* Receiving side: show pending invitations with board name/description, inviter, created time, and Accept / Decline actions.
* Managing side: for boards owned by current user, provide board selector, username input, pending invitation list, and revoke action.
* Notification integration: a `board_invite` notification can link to `/invites`.
* Left rail still remains the discovery surface: accepted invite-only boards appear under「邀请版块」; pending invitations do not reveal private content outside `/invites`.
* Create-board UI: regular users see a simple “创建邀请版块” flow; no public/private selector is shown to them.
