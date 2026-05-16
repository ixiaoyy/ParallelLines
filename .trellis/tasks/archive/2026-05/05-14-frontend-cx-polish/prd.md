# PRD: Frontend CX Problem-Solving Redesign

## Goal

Refactor the 平行线 forum home/topic discovery experience from a community-activity dashboard into a problem-solving entry point. The page should help a technical user quickly search, identify solved/unanswered topics, choose the right intent path, and enter a useful thread with minimal cognitive load.

## CX Problem Statement

Current home UI over-emphasizes visual polish and community activity:

- Large hero and metrics push the topic list below the most valuable first-screen area.
- Sidebar and left taxonomy compete with the main topic discovery task.
- Category labels reflect internal/community structure more than user intent.
- Participant avatars occupy prominent list real estate but do not help users judge answer quality.
- Solved/unanswered/official-response states are not prominent enough.
- Low-contrast meta text and subtle labels risk accessibility failures.
- Composer/search/publishing entry points are distributed inconsistently.

## Target User Path

Primary path:

1. User lands on home page with a technical problem.
2. User searches by symptom, error code, API name, or keyword.
3. User narrows by intent: 已解决, 未回复, 官方回复, 热门, 最新.
4. User scans topic cards and can identify answer status without opening every topic.
5. User opens a relevant thread or starts a new topic from a clear CTA.

Secondary path:

1. User browses by board/category after search/intent filters fail.
2. User sees concise board guidance and high-signal topics.

## Requirements

### P0 Requirements

- Replace oversized home hero with a compact search-first problem-solving header.
- Ensure a 1366px desktop first screen shows the search entry plus at least 3 topic rows.
- Promote topic resolution state in `TopicCard`: 已解决, 未回复, 官方回复/精华, 已关闭.
- Demote participant avatars from a primary column to secondary metadata or compact footer.
- Remove or collapse vanity metrics (`今日新帖`, `正在编辑`, `本周已解决`) unless converted to actionable metrics.
- Reduce right sidebar to at most 2 modules on desktop first screen.
- Remove always-visible composer from home sidebar; use a clear CTA that opens/links to composer flow.
- Raise meta text and status contrast to meet the frontend accessibility quality bar.

### P1 Requirements

- Add intent-oriented quick filters: 我要排障, 找最佳实践, 看版本公告, 提需求/投票, 查已解决.
- Make search placeholder and helper copy focus on symptoms/error codes/API names.
- Add empty state guidance when a filter/search has no matching fixture/API topics.
- Keep board navigation available, but below the problem-solving path.

## Acceptance Criteria

- [ ] Home first screen no longer feels like a marketing/operations dashboard.
- [ ] At 1366px desktop width, at least 3 topic cards are visible without scrolling.
- [ ] Topic cards make solved/unanswered/official/closed state scannable within 1 second.
- [ ] Right sidebar contains no more than 2 modules above the fold.
- [ ] Participant avatars no longer consume a full primary list column.
- [ ] Search and publish CTAs have one consistent location and expectation.
- [ ] Topic/meta text contrast is visibly stronger than the current muted gray treatment.
- [ ] `pnpm --dir apps/web lint`, `pnpm --dir apps/web typecheck`, and `pnpm --dir apps/web build` pass.

## Technical Notes

- Primary files likely affected:
  - `apps/web/src/pages/home/HomePage.vue`
  - `apps/web/src/pages/home/HomePage.scss`
  - `apps/web/src/features/topics/components/TopicCard.vue`
  - `apps/web/src/features/topics/components/TopicCard.scss`
  - `apps/web/src/features/topics/components/TopicList.vue`
  - `apps/web/src/features/topics/components/TopicList.scss`
  - `apps/web/src/shared/api/mockForum.ts`
- Preserve the existing Calm Tech palette tokens; improve hierarchy through layout, spacing, font weight, and contrast.
- Keep copy in Simplified Chinese technical forum language.
- This task is frontend-only unless API fields need explicit solved/unanswered/official flags later.

## Source Feedback

This task comes from a CX critique of the current screenshot/UI. Key critique themes:

- The design looks polished but sacrifices logic.
- The homepage creates a maze instead of a problem-solving path.
- Activity metrics feel self-congratulatory rather than useful.
- Status feedback is too weak for users who need solved answers quickly.
- Sidebar density and low contrast increase cognitive load.


## Screenshot-Specific CX Findings

### Board Directory Page (`/boards`)

Source screenshot: `C:/Users/phpxi/Downloads/screencapture-127-0-0-1-5173-boards-2026-05-14-16_53_38.png`

#### P0 Problems

- Board initials (`支`, `开`, `插`, `社`) create a false threshold for first-time visitors. They look like internal codes and force users to decode abbreviations before understanding where to click.
- The hero copy (`选择一条平行线，进入对应的问题现场`) is too literary for a support/discovery page. It delays the user who arrives with a concrete error code or API problem.
- Board cards expose `关注版块` / `调整通知` as primary actions before the visitor has chosen a board or logged in. This pushes subscription mechanics too early and creates trust friction.
- The page prioritizes board marketing cards over task intent. Users have to infer whether they should choose `支持与排障`, `开发与 API`, or `插件与主题`.
- Pale blue/gray surfaces and subtle buttons can be misread as disabled or unfinished loading states.

#### Required Fix Direction

- Replace single-character board marks with explicit icon + full board name, or keep initials only as decorative marks next to readable labels.
- Replace literary hero copy with utility-first copy, e.g. `搜索错误码、API 名称或问题现象，直接找到相关主题。`
- Add a prominent search box and intent shortcuts above board cards.
- Demote follow/notification actions for anonymous/first-time visitors; primary card CTA should be `查看相关问题` / `进入版块`.
- Add visitor-safe helper text: `不确定选哪个？先搜索问题或从“我要排障”开始。`

### Support Board Page (`/b/support`)

Source screenshot: `C:/Users/phpxi/Downloads/screencapture-127-0-0-1-5173-b-support-2026-05-14-16_54_24.png`

#### P0 Problems

- Search is visually weak despite being the main lifeline for visitors looking for concrete solutions.
- The board hero, large title, oversized mark, and metric cards consume too much first-screen space; only two topic rows are visible.
- Board-level counters (`主题 1520`, `帖子 1.5万`, `关注 3.5万`) are less useful than solution-oriented signals like `已解决`, `未回复`, `平均响应`.
- Sidebar modules (`发帖规则`, `值班版主`, `相关标签`, `相邻版块`) compete with the topic list, while the visitor's main goal is case comparison.
- Topic list still dedicates a primary column to participant avatars. This does not help judge whether a thread contains an answer.

#### Required Fix Direction

- Make board pages search-first: a strong local search/search-helper block should appear above filters.
- Compress the board hero to a utility header: board name, purpose, search, and primary filters in one compact area.
- Replace large counters with answer-quality signals: `已解决`, `等待回复`, `平均首次响应`, `官方回复`.
- Show at least 4 topic rows above the fold at 1366px desktop width on board detail pages.
- Collapse sidebar modules below the fold or reduce to one contextual module (`发帖前请确认`) until the user scrolls.
- Make solved/unanswered/official state more prominent than avatars and raw view counts.

## Page-Specific Acceptance Criteria

### Board Directory

- [ ] No board selection depends on decoding a single-character abbreviation.
- [ ] The first visible page block uses task-oriented copy, not literary/brand copy.
- [ ] Search and intent shortcuts are visually stronger than board stats.
- [ ] Anonymous visitor primary CTA is `查看相关问题` / `进入版块`, not `关注版块`.
- [ ] Follow/notification controls are hidden, secondary, or clearly marked as logged-in actions.

### Support Board Detail

- [ ] `/b/support` desktop first screen shows local search and at least 4 topic rows at 1366px width.
- [ ] Search box has stronger contrast and width than passive metric cards.
- [ ] Board hero is compact enough that topic comparison begins immediately.
- [ ] Board metrics are solution-oriented, not community vanity metrics.
- [ ] Sidebar above the fold has at most one helper module.
- [ ] Topic row state (`已解决`, `未回复`, `官方回复`, `已关闭`) is more prominent than participant avatars.

## Implementation Slices

1. Board directory CX cleanup:
   - Rewrite hero copy.
   - Add prominent problem search/intent shortcuts.
   - Replace initial-only marks with readable board identity.
   - Demote follow/notification buttons.
2. Support board detail CX cleanup:
   - Compress board hero.
   - Promote local search and problem-state filters.
   - Increase above-fold topic density.
   - Collapse/reduce sidebar.
3. Topic list/status cleanup:
   - Reweight `TopicCard` layout around answer status and scannability.
   - Remove participant-avatar primary column from list views.
   - Strengthen contrast for meta/status text.
