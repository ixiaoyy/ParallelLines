# 主题市场、组件安装与安全沙箱

## Goal

支持安装/更新/回滚主题和主题组件，并隔离不可信代码风险。

## Requirements

- 管理员可上传或安装主题包。
- 主题可配置变量、资源和组件插槽。
- 支持预览、启用、回滚。
- 限制危险脚本和外链资源。

## Acceptance Criteria

- [ ] 主题启用后全站样式变化。
- [ ] 回滚恢复旧主题。
- [ ] 非法主题包被拒绝。

## Priority

- `P2`：Discourse parity roadmap 中的排期优先级。

## Technical Notes

当前可先做内部主题配置，市场化放后续。

## Relevant Context

- Parent roadmap: `.trellis/tasks/05-20-discourse-parity-roadmap`
- Source comparison: `D:\work\ParallelLines` vs `D:\work\discourse`
- Implement with project specs under `.trellis/spec/` and update specs when contracts change.
