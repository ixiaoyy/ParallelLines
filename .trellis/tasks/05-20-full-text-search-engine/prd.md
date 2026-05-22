# 正式全文搜索与搜索分析

## Goal

从 SQL LIKE 升级为可运营全文搜索，支持索引、相关性、权限过滤和搜索日志。

## Requirements

- 建立搜索索引适配层，可对接数据库全文索引或 Meilisearch/OpenSearch。
- 索引主题、帖子、标签、作者，并支持权限过滤。
- 支持高级筛选：版块、标签、作者、时间、状态。
- 记录搜索日志，用于无结果分析和热词。
- 内容更新、隐藏、恢复、删除后索引同步。

## Acceptance Criteria

- [x] 搜索结果按相关性和时间稳定排序。
- [x] 隐藏/私密内容不向未授权用户出现在搜索结果。
- [x] 更新帖子后搜索索引同步更新。
- [x] 测试覆盖索引同步、权限过滤和特殊字符。

## Priority

- `P0`：Discourse parity roadmap 中的排期优先级。

## Technical Notes

当前 list_topics/search 是 LIKE MVP，需要适配层避免锁死技术选型。

## Relevant Context

- Parent roadmap: `.trellis/tasks/05-20-discourse-parity-roadmap`
- Source comparison: `D:\work\ParallelLines` vs `D:\work\discourse`
- Implement with project specs under `.trellis/spec/` and update specs when contracts change.
