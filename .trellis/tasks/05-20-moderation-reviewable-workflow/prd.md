# 审核 Reviewable 工作流与申诉

## Goal

在基础举报队列之上建立统一审核对象、分配、认领、处理理由、自动规则和申诉机制。

## Requirements

- 统一 reviewable 对象承载举报、敏感内容待审、新用户发帖待审等。
- 审核员可认领/释放审核项，避免多人冲突处理。
- 处理动作支持通过、拒绝、隐藏、删除、禁言、升级处理。
- 用户可查看自己的待审/被处理通知并发起申诉。
- 自动规则生成的审核项需标明来源和可解释摘要。

## Acceptance Criteria

- [ ] 敏感内容可进入待审而不是只能阻止/替换。
- [ ] 审核项认领后其他审核员看到状态变化。
- [ ] 所有处理写审计并通知相关用户。
- [ ] 普通用户不能访问审核详情但能看到自己的申诉入口。

## Priority

- `P0`：Discourse parity roadmap 中的排期优先级。

## Technical Notes

当前 flags/audit_logs 已有基础，可渐进迁移。

## Relevant Context

- Parent roadmap: `.trellis/tasks/05-20-discourse-parity-roadmap`
- Source comparison: `D:\work\ParallelLines` vs `D:\work\discourse`
- Implement with project specs under `.trellis/spec/` and update specs when contracts change.
