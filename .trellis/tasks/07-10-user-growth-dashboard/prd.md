# 增加用户增长看板并排除马甲账号

## Goal

在后台访问统计页增加真实用户增长看板，并以持久化账号标记确保马甲账号不会进入注册增长统计。

## Requirements

- 为用户数据增加明确的马甲账号标记，普通注册默认不是马甲。
- 数据迁移回填当前已配置的 23 个马甲账号，后续 persona seed/upsert 继续写入该标记。
- 后台 analytics 的逐日注册数、区间注册总数和 daily activity 报表统一排除马甲账号。
- 访问统计页使用现有日期范围展示区间新增用户与每日新增趋势，并明确标注“不含马甲账号”。
- 不通过用户名模糊匹配或邮箱域名推断马甲身份。

## Acceptance Criteria

- [ ] 普通用户注册记录计入增长数据，`is_persona=true` 的用户不计入。
- [ ] overview totals、daily series 与 daily activity 报表使用相同过滤口径。
- [ ] 现有 23 个 persona 登录账号在迁移后均被标记。
- [ ] 用户增长看板响应 7/30/90 天及自定义日期范围，并随刷新更新。
- [ ] 前端类型检查、lint、相关后端静态检查与 OpenAPI 漂移检查通过。

## Technical Notes

- 使用 `users.is_persona` 作为唯一业务标记，默认 `false`，不向公开用户 DTO 暴露。
- 前端复用现有 `AnalyticsMetricPoint.registrations` 与 `AnalyticsTotalsResponse.registrations`，不新增重复查询。
- 本地 API 测试依赖已配置的 MySQL 测试库；未确认数据库可用时只做项目约定的轻量验证。
