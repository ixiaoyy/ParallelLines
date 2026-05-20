# AI 摘要、推荐与审核辅助

## Goal

为长主题摘要、相似主题推荐、自动标签和审核辅助预留 AI 能力。

## Requirements

- 生成主题摘要和关键回复。
- 发帖时推荐相似主题和标签。
- 审核台提供风险摘要和处理建议。
- AI 输出需有人工确认和成本控制。

## Acceptance Criteria

- [ ] 长主题可生成摘要且可刷新。
- [ ] 新主题输入时返回相似主题。
- [ ] 审核建议不自动执行高风险动作。

## Priority

- `P2`：Discourse parity roadmap 中的排期优先级。

## Technical Notes

对应 discourse-ai；需要隐私和成本边界。

## Relevant Context

- Parent roadmap: `.trellis/tasks/05-20-discourse-parity-roadmap`
- Source comparison: `D:\work\ParallelLines` vs `D:\work\discourse`
- Implement with project specs under `.trellis/spec/` and update specs when contracts change.
