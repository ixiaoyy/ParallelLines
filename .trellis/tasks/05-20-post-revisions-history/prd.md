# 帖子编辑历史、版本对比与恢复

## Goal

记录帖子编辑版本，支持作者/版主查看差异、恢复版本和审计编辑行为。

## Requirements

- 每次编辑保存旧 raw_md/cooked_html、编辑人、原因和时间。
- 作者和具备权限的版主可查看版本历史。
- 版主可恢复指定历史版本，恢复也写入新版本和审计日志。
- 公开视图只展示当前版本，不泄露被隐藏/已删除内容。
- 支持编辑原因或自动生成摘要。

## Acceptance Criteria

- [ ] 编辑首楼后可查询版本列表和版本详情。
- [ ] 普通用户不能查看他人私密/隐藏内容历史。
- [ ] 恢复旧版本后帖子内容和搜索索引一致。
- [ ] 测试覆盖作者、陌生人、版主权限边界。

## Priority

- `P0`：Discourse parity roadmap 中的排期优先级。

## Technical Notes

对齐 Discourse post_revision/post_custom_field 类能力。

## Relevant Context

- Parent roadmap: `.trellis/tasks/05-20-discourse-parity-roadmap`
- Source comparison: `D:\work\ParallelLines` vs `D:\work\discourse`
- Implement with project specs under `.trellis/spec/` and update specs when contracts change.
