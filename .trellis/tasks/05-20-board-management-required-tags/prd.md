# 版块管理、子版块、必填标签与默认策略

## Goal

扩展版块能力：子版块、版主、默认通知、必填标签、发帖模板和版块设置。

## Requirements

- 支持子版块/层级展示。
- 版块 owner 可配置版主和成员角色。
- 支持版块必填标签、允许标签组、发帖模板。
- 支持版块默认通知等级和默认排序。

## Acceptance Criteria

- [ ] 未带必填标签发帖失败。
- [ ] 版主权限只作用于对应版块。
- [ ] 子版块在列表和路由中展示正确。
- [ ] 测试覆盖配置权限。

## Priority

- `P1`：Discourse parity roadmap 中的排期优先级。

## Technical Notes

与邀请版块 ACL 强相关。

## Relevant Context

- Parent roadmap: `.trellis/tasks/05-20-discourse-parity-roadmap`
- Source comparison: `D:\work\ParallelLines` vs `D:\work\discourse`
- Implement with project specs under `.trellis/spec/` and update specs when contracts change.
