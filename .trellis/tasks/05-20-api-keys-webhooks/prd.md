# API Key、Webhook 与外部系统接入

## Goal

提供安全的 API key、作用域、Webhook 事件投递、签名和重试机制。

## Requirements

- 管理员可创建带 scope 的 API key。
- 用户可创建个人 API token（可选）。
- Webhook 支持主题/回复/用户/审核事件。
- Webhook 请求带签名、重试和投递日志。

## Acceptance Criteria

- [ ] 无 scope 的 key 不能访问接口。
- [ ] Webhook 接收方失败会重试并记录。
- [ ] 管理员可禁用 key/webhook。
- [ ] 测试覆盖签名和权限。

## Priority

- `P1`：Discourse parity roadmap 中的排期优先级。

## Technical Notes

依赖后台任务体系更稳。

## Relevant Context

- Parent roadmap: `.trellis/tasks/05-20-discourse-parity-roadmap`
- Source comparison: `D:\work\ParallelLines` vs `D:\work\discourse`
- Implement with project specs under `.trellis/spec/` and update specs when contracts change.
