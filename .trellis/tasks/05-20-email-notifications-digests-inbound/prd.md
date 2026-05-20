# 邮件通知、摘要邮件与入站回复

## Goal

补齐真实论坛的邮件触达：通知邮件、摘要邮件、退信处理和邮件回复入站。

## Requirements

- 站内通知可按用户偏好发送邮件。
- 支持每日/每周摘要邮件，包含关注版块/主题更新。
- 邮件模板可配置并支持基础品牌。
- 处理退信/投诉，自动降低邮件发送或标记邮箱异常。
- 支持通过邮件回复主题/帖子，首版可先设计入站 webhook 合约。

## Acceptance Criteria

- [ ] 被回复/提及时可收到邮件通知。
- [ ] 用户可关闭特定类型邮件。
- [ ] 摘要任务只发送给符合条件的活跃用户。
- [ ] 退信 webhook 会记录邮件状态。

## Priority

- `P0`：Discourse parity roadmap 中的排期优先级。

## Technical Notes

依赖后台任务体系；可先做通知邮件和偏好，再做 digest/inbound。

## Relevant Context

- Parent roadmap: `.trellis/tasks/05-20-discourse-parity-roadmap`
- Source comparison: `D:\work\ParallelLines` vs `D:\work\discourse`
- Implement with project specs under `.trellis/spec/` and update specs when contracts change.
