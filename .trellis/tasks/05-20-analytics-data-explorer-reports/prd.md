# 数据报表、运营分析与 Data Explorer

## Goal

补齐运营报表、趋势分析、管理员查询和导出能力。

## Requirements

- 统计 DAU/MAU、注册、发帖、回复、点赞、举报等指标。
- 后台展示趋势图和 Top 列表。
- 管理员可运行受限查询或预设报表。
- 支持 CSV 导出。

## Acceptance Criteria

- [ ] 报表数据可按日期范围筛选。
- [ ] 普通用户不能访问后台报表。
- [ ] 导出任务有权限和审计。

## Priority

- `P2`：Discourse parity roadmap 中的排期优先级。

## Technical Notes

参考 Discourse reports/data-explorer。

## Relevant Context

- Parent roadmap: `.trellis/tasks/05-20-discourse-parity-roadmap`
- Source comparison: `D:\work\ParallelLines` vs `D:\work\discourse`
- Implement with project specs under `.trellis/spec/` and update specs when contracts change.
