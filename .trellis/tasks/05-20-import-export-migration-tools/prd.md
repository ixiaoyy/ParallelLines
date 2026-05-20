# 导入、导出与迁移工具

## Goal

支持从其他论坛/CSV/Markdown 导入数据，以及面向迁移的导出工具。

## Requirements

- 定义导入格式和映射规则。
- 支持用户、版块、主题、帖子、标签导入。
- 导入过程可预演、断点续传和错误报告。
- 导出可用于迁移到其他系统。

## Acceptance Criteria

- [ ] 小型样例数据可完整导入。
- [ ] 重复导入不会生成重复对象。
- [ ] 错误行有报告。

## Priority

- `P2`：Discourse parity roadmap 中的排期优先级。

## Technical Notes

Discourse 有大量 import scripts；本项目后置。

## Relevant Context

- Parent roadmap: `.trellis/tasks/05-20-discourse-parity-roadmap`
- Source comparison: `D:\work\ParallelLines` vs `D:\work\discourse`
- Implement with project specs under `.trellis/spec/` and update specs when contracts change.
