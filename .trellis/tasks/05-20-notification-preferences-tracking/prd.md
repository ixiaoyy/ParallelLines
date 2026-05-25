# 通知偏好、跟踪状态与免打扰

## Goal

补齐 watching/tracking/muted、邮件/站内偏好、免打扰和已读游标。

## Requirements

- 用户可对主题/版块设置 watching/tracking/normal/muted。
- 通知生成遵循用户偏好和免打扰时间。
- 支持批量已读、未读计数和跨端同步。
- 邮件通知读取同一偏好来源。

## Acceptance Criteria

- [x] muted 主题不再产生通知。
- [x] watching 版块新主题/回复会通知。
- [x] 免打扰期间不推送即时邮件通知。
- [x] 测试覆盖偏好矩阵。

## Priority

- `P1`：Discourse parity roadmap 中的排期优先级。

## Technical Notes

当前 TopicRead 有 notification_level，可扩展。

## Relevant Context

- Parent roadmap: `.trellis/tasks/05-20-discourse-parity-roadmap`
- Source comparison: `D:\work\ParallelLines` vs `D:\work\discourse`
- Implement with project specs under `.trellis/spec/` and update specs when contracts change.
