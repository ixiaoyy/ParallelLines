# 已解决、投票、问答与 Poll 能力

## Goal

补齐常见技术论坛互动模式：解决方案标记、主题/帖子投票、问答排序和投票组件。

## Requirements

- 作者/版主可将某回复标记为解决方案。
- 支持主题或帖子投票/赞成反对。
- 问答模式可按投票和采纳排序。
- 支持简单 poll：单选/多选、截止时间、权限。

## Acceptance Criteria

- [x] 解决方案在列表和详情有标识。
- [x] 重复投票幂等且计数正确。
- [x] Poll 截止后不能继续投票。
- [x] 测试覆盖权限和计数。

## Priority

- `P1`：Discourse parity roadmap 中的排期优先级。

## Technical Notes

对应 discourse-solved/post-voting/topic-voting/poll 类能力。

## Relevant Context

- Parent roadmap: `.trellis/tasks/05-20-discourse-parity-roadmap`
- Source comparison: `D:\work\ParallelLines` vs `D:\work\discourse`
- Implement with project specs under `.trellis/spec/` and update specs when contracts change.
