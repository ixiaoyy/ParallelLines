# 移动端适配、PWA 与推送通知

## Goal

提升移动端论坛体验，支持 PWA 安装、离线页和 Web Push。

## Requirements

- 关键页面移动端布局优化。
- 提供 manifest、service worker 和离线页。
- 支持 Web Push 订阅和撤销。
- 推送遵守通知偏好。

## Acceptance Criteria

- [ ] 移动端发帖/回复/审核可用。
- [ ] 用户可安装 PWA。
- [ ] 通知推送可收到并点击跳转。

## Priority

- `P2`：Discourse parity roadmap 中的排期优先级。

## Technical Notes

依赖通知偏好和后台任务。

## Relevant Context

- Parent roadmap: `.trellis/tasks/05-20-discourse-parity-roadmap`
- Source comparison: `D:\work\ParallelLines` vs `D:\work\discourse`
- Implement with project specs under `.trellis/spec/` and update specs when contracts change.
