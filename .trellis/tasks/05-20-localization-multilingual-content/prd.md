# 多语言内容、本地化与翻译工作流

## Goal

支持多语言 UI、内容本地化、翻译覆盖和语言偏好。

## Requirements

- 用户可设置界面语言。
- 版块/主题可存储本地化标题/摘要。
- 管理员可维护翻译覆盖。
- 搜索和 SEO 考虑语言维度。

## Acceptance Criteria

- [ ] 切换语言后 UI 文案变化。
- [ ] 本地化主题标题按语言展示。
- [ ] 缺失翻译 fallback 到默认语言。

## Priority

- `P2`：Discourse parity roadmap 中的排期优先级。

## Technical Notes

对应 Discourse localizable/topic_localization/post_localization。

## Relevant Context

- Parent roadmap: `.trellis/tasks/05-20-discourse-parity-roadmap`
- Source comparison: `D:\work\ParallelLines` vs `D:\work\discourse`
- Implement with project specs under `.trellis/spec/` and update specs when contracts change.
