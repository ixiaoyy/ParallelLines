# 徽章与信任等级体系

## Goal

在积分经验之外，建立可运营的徽章、信任等级和自动授权规则。

## Requirements

- 定义 trust_level 与角色分离。
- 按行为授予徽章并记录授予流水。
- 信任等级影响频控、上传、发链接、审核前置等规则。
- 管理员可手动授予/撤销徽章。

## Acceptance Criteria

- [ ] 用户达成条件自动获得徽章。
- [ ] 信任等级变更写日志且不等同管理员权限。
- [ ] 低信任用户受更严格风控。
- [ ] 测试覆盖等级边界。

## Priority

- `P1`：Discourse parity roadmap 中的排期优先级。

## Technical Notes

与 user-points-experience 不重复；level 可偏展示，trust_level 偏权限/风控。

## Relevant Context

- Parent roadmap: `.trellis/tasks/05-20-discourse-parity-roadmap`
- Source comparison: `D:\work\ParallelLines` vs `D:\work\discourse`
- Implement with project specs under `.trellis/spec/` and update specs when contracts change.
