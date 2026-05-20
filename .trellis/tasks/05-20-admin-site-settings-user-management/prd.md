# 后台站点设置、用户管理与系统面板

## Goal

从单一审核台扩展为可运营后台：用户管理、站点设置、系统健康、邮件日志与审计。

## Requirements

- 管理员可搜索用户、查看详情、调整角色/状态/等级相关字段。
- 提供站点设置表和 API，支持修改基础配置、品牌、注册开关、上传限制等。
- 后台展示系统健康：队列、邮件、数据库、缓存、版本和关键错误。
- 整合邮件日志、审核日志、管理员操作日志。
- 所有后台写操作需要 admin 权限和审计日志。

## Acceptance Criteria

- [ ] 普通用户访问后台接口返回 403。
- [ ] 管理员可修改站点设置并在前端生效。
- [ ] 用户管理操作写入审计日志。
- [ ] 系统面板可展示关键服务状态和最近错误。

## Priority

- `P0`：Discourse parity roadmap 中的排期优先级。

## Technical Notes

参考 Discourse admin/* controllers。

## Relevant Context

- Parent roadmap: `.trellis/tasks/05-20-discourse-parity-roadmap`
- Source comparison: `D:\work\ParallelLines` vs `D:\work\discourse`
- Implement with project specs under `.trellis/spec/` and update specs when contracts change.
