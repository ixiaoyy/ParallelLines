# 账号找回与登录安全

## Goal

补齐忘记密码、修改密码/邮箱、登录设备管理、2FA 和 OAuth/SSO 基础能力。

## Requirements

- 支持忘记密码邮件令牌、重置密码和令牌失效。
- 支持登录用户修改密码和发起邮箱变更验证。
- 记录会话/登录设备，支持用户主动注销其他会话。
- 支持 TOTP 二次验证的启用、校验、恢复码和禁用。
- 预留 OAuth/SSO 登录适配层，首版可接入一个 provider 或提供清晰接口。

## Acceptance Criteria

- [ ] 忘记密码流程不会泄露邮箱是否存在。
- [ ] 重置/邮箱变更令牌一次性、过期后不可复用。
- [ ] 启用 2FA 后登录必须完成二次校验。
- [ ] 用户可查看并撤销自己的活动会话。
- [ ] 认证相关测试覆盖普通/过期/重复/攻击路径。

## Priority

- `P0`：Discourse parity roadmap 中的排期优先级。

## Technical Notes

与已完成邮箱验证码注册对齐，复用邮件服务但使用独立 token 类型。

## Relevant Context

- Parent roadmap: `.trellis/tasks/05-20-discourse-parity-roadmap`
- Source comparison: `D:\work\ParallelLines` vs `D:\work\discourse`
- Implement with project specs under `.trellis/spec/` and update specs when contracts change.
