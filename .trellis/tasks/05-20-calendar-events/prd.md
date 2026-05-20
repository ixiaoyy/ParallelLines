# 日历、活动与本地时间

## Goal

支持社区活动、日历订阅、时区本地化和提醒。

## Requirements

- 用户可创建活动主题或事件。
- 支持 RSVP/报名和人数限制。
- 展示用户本地时区时间。
- 提供 iCal 订阅。

## Acceptance Criteria

- [ ] 活动可在日历视图展示。
- [ ] 报名截止后不能继续报名。
- [ ] 提醒通知按用户时区发送。

## Priority

- `P2`：Discourse parity roadmap 中的排期优先级。

## Technical Notes

对应 discourse-calendar/local-dates。

## Relevant Context

- Parent roadmap: `.trellis/tasks/05-20-discourse-parity-roadmap`
- Source comparison: `D:\work\ParallelLines` vs `D:\work\discourse`
- Implement with project specs under `.trellis/spec/` and update specs when contracts change.
