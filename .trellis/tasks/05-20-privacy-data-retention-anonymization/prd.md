# 隐私、数据保留、匿名化与账号删除

## Goal

提供真实社区需要的数据隐私能力：导出、匿名化、账号删除、保留策略和日志脱敏。

## Requirements

- 用户可请求导出个人数据。
- 管理员可匿名化用户并保留内容归属占位。
- 账号删除需处理帖子、私信、上传和审计关系。
- 日志和导出不包含 token/hash 等敏感数据。

## Acceptance Criteria

- [ ] 匿名化后用户名/email 不再可识别。
- [ ] 删除流程不破坏主题阅读。
- [ ] 导出仅包含本人有权数据。
- [ ] 测试覆盖敏感字段排除。

## Priority

- `P1`：Discourse parity roadmap 中的排期优先级。

## Technical Notes

参考 Discourse user_anonymizer/user_destroyer。

## Relevant Context

- Parent roadmap: `.trellis/tasks/05-20-discourse-parity-roadmap`
- Source comparison: `D:\work\ParallelLines` vs `D:\work\discourse`
- Implement with project specs under `.trellis/spec/` and update specs when contracts change.
