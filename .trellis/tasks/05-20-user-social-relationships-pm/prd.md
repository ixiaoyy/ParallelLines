# 用户关注、忽略/屏蔽与私信

## Goal

实现用户关系和私密交流能力：关注用户、忽略/屏蔽用户、私信主题。

## Requirements

- 用户可关注/取消关注其他用户。
- 用户可忽略或屏蔽他人，影响通知和内容展示。
- 支持一对一/多人私信主题，权限隔离。
- 被屏蔽用户交互需遵守边界。

## Acceptance Criteria

- [ ] 关注用户发帖可产生通知或动态。
- [ ] 屏蔽用户后不收到其通知。
- [ ] 私信内容仅参与者可见。
- [ ] 测试覆盖私信越权。

## Priority

- `P1`：Discourse parity roadmap 中的排期优先级。

## Technical Notes

Discourse 使用 private message topic；可复用 Topic 加 visibility/type。

## Relevant Context

- Parent roadmap: `.trellis/tasks/05-20-discourse-parity-roadmap`
- Source comparison: `D:\work\ParallelLines` vs `D:\work\discourse`
- Implement with project specs under `.trellis/spec/` and update specs when contracts change.
