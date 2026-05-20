# 用户设置、公开目录与个人资料完善

## Goal

扩展用户中心：资料编辑、偏好设置、公开用户目录、隐私设置和活动页。

## Requirements

- 用户可编辑昵称/简介/头像/链接等资料。
- 用户可配置隐私、通知、邮件和界面偏好。
- 提供用户目录，支持按活跃度/等级/贡献排序。
- 用户活动页展示回复、点赞、收藏等。

## Acceptance Criteria

- [ ] 资料修改后 API 和页面一致。
- [ ] 隐私设置影响公开字段。
- [ ] 用户目录不泄露邮箱。
- [ ] 测试覆盖本人/他人权限。

## Priority

- `P1`：Discourse parity roadmap 中的排期优先级。

## Technical Notes

当前只有公开 profile 和主题列表。

## Relevant Context

- Parent roadmap: `.trellis/tasks/05-20-discourse-parity-roadmap`
- Source comparison: `D:\work\ParallelLines` vs `D:\work\discourse`
- Implement with project specs under `.trellis/spec/` and update specs when contracts change.
