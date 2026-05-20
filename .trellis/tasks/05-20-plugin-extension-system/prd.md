# 插件扩展系统与事件 Hook

## Goal

设计可扩展插件点、事件 hook、前端插槽和安全边界，为生态功能预留入口。

## Requirements

- 定义后端事件 hook 和服务扩展点。
- 定义前端页面/组件扩展插槽。
- 插件配置与启停可被管理员管理。
- 插件错误隔离，不能拖垮核心请求。

## Acceptance Criteria

- [ ] 示例插件可注册一个事件和一个 UI 入口。
- [ ] 禁用插件后扩展消失。
- [ ] 插件异常被记录且核心功能可用。

## Priority

- `P2`：Discourse parity roadmap 中的排期优先级。

## Technical Notes

Discourse 生态高度依赖插件；本项目先做最小扩展框架。

## Relevant Context

- Parent roadmap: `.trellis/tasks/05-20-discourse-parity-roadmap`
- Source comparison: `D:\work\ParallelLines` vs `D:\work\discourse`
- Implement with project specs under `.trellis/spec/` and update specs when contracts change.
