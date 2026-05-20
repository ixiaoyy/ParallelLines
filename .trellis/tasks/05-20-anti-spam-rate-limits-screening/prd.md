# 反垃圾、频控与屏蔽名单

## Goal

实现发帖/注册/举报等关键路径的频控、IP/邮箱/URL 屏蔽、自动禁言和信任边界。

## Requirements

- 对注册、登录、发主题、回复、上传、举报等写操作增加用户/IP 维度频控。
- 维护 screened_emails、screened_ip_addresses、screened_urls 或等价屏蔽名单。
- 支持新用户高风险内容进入审核或自动禁言。
- 频控和屏蔽错误不泄露敏感策略细节。
- 管理员可查看/新增/移除屏蔽规则和自动处置记录。

## Acceptance Criteria

- [ ] 重复发帖/注册达到阈值时返回 rate_limited。
- [ ] 命中屏蔽邮箱/IP/URL 时写操作被阻止或进入审核。
- [ ] 管理员可管理屏蔽规则并看到审计日志。
- [ ] 测试覆盖用户/IP 双维度和绕过边界。

## Priority

- `P0`：Discourse parity roadmap 中的排期优先级。

## Technical Notes

可先用数据库规则 + Redis/内存计数；生产需 Redis。

## Relevant Context

- Parent roadmap: `.trellis/tasks/05-20-discourse-parity-roadmap`
- Source comparison: `D:\work\ParallelLines` vs `D:\work\discourse`
- Implement with project specs under `.trellis/spec/` and update specs when contracts change.
