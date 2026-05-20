# GitHub、Zendesk、Patreon 等外部集成

## Goal

实现常见社区外部集成框架和若干 provider。

## Requirements

- GitHub 登录/仓库链接/issue 展开。
- Zendesk 工单联动。
- Patreon/会员系统同步。
- 集成配置可后台管理。

## Acceptance Criteria

- [ ] 至少一个 provider 端到端可用。
- [ ] 配置缺失时有后台问题检查。
- [ ] Webhook 验签和重试。

## Priority

- `P2`：Discourse parity roadmap 中的排期优先级。

## Technical Notes

可在 API/Webhook 基础上做。

## Relevant Context

- Parent roadmap: `.trellis/tasks/05-20-discourse-parity-roadmap`
- Source comparison: `D:\work\ParallelLines` vs `D:\work\discourse`
- Implement with project specs under `.trellis/spec/` and update specs when contracts change.
