# 备份、恢复与数据导出

## Goal

实现论坛数据备份、恢复、下载导出与管理员可用的灾备流程。

## Requirements

- 管理员可触发数据库/上传文件备份并查看备份列表。
- 备份文件带元数据、校验和、创建人、创建时间和版本。
- 支持安全下载和删除旧备份。
- 恢复流程需有显式确认、权限检查和环境保护。
- 用户可导出自己的数据，管理员可导出全站数据。

## Acceptance Criteria

- [x] 备份任务成功生成可下载归档和校验信息。
- [x] 非管理员无法触发或下载全站备份。
- [x] 失败备份有日志和状态。
- [x] 导出文件不包含明文密码/token。

## Priority

- `P0`：Discourse parity roadmap 中的排期优先级。

## Technical Notes

生产恢复危险，先实现备份与导出，恢复需额外确认。

## Relevant Context

- Parent roadmap: `.trellis/tasks/05-20-discourse-parity-roadmap`
- Source comparison: `D:\work\ParallelLines` vs `D:\work\discourse`
- Implement with project specs under `.trellis/spec/` and update specs when contracts change.

