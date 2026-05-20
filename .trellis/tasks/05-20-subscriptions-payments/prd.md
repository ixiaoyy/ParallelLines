# 订阅、付费会员与支付集成

## Goal

为付费社区预留订阅、会员权益、支付 webhook 和账单能力。

## Requirements

- 定义会员计划和权益。
- 接入支付 provider webhook。
- 订阅状态影响版块/功能访问。
- 账单和失败支付可追踪。

## Acceptance Criteria

- [ ] 支付成功后用户获得权益。
- [ ] 订阅过期后权益撤销。
- [ ] Webhook 签名校验。

## Priority

- `P2`：Discourse parity roadmap 中的排期优先级。

## Technical Notes

对应 discourse-subscriptions，优先放 P2。

## Relevant Context

- Parent roadmap: `.trellis/tasks/05-20-discourse-parity-roadmap`
- Source comparison: `D:\work\ParallelLines` vs `D:\work\discourse`
- Implement with project specs under `.trellis/spec/` and update specs when contracts change.
