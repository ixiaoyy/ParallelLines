# 主题生命周期：关闭、置顶、移动、拆分与合并

## Goal

补齐真实论坛主题管理操作，包括状态控制、跨版块移动、拆分回复、合并主题和审计。

## Requirements

- 版主可关闭/打开/归档/置顶/取消置顶主题。
- 版主可将主题移动到其他有权限版块。
- 版主可将一组回复拆分成新主题。
- 版主可合并两个主题并保持楼层、通知和跳转关系。
- 所有操作写审计日志并刷新计数、搜索和 Feed。

## Acceptance Criteria

- [ ] 关闭主题后普通用户不能回复。
- [ ] 移动主题后旧链接可跳转或返回明确状态。
- [ ] 拆分/合并后 reply_count、post_number、通知不漂移。
- [ ] 普通用户不能执行生命周期操作。

## Priority

- `P0`：Discourse parity roadmap 中的排期优先级。

## Technical Notes

这是高风险跨层任务，应分步实现状态控制 -> 移动 -> 拆分/合并。

## Relevant Context

- Parent roadmap: `.trellis/tasks/05-20-discourse-parity-roadmap`
- Source comparison: `D:\work\ParallelLines` vs `D:\work\discourse`
- Implement with project specs under `.trellis/spec/` and update specs when contracts change.
