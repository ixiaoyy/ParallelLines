# 站点主题、品牌配置与文案国际化

## Goal

支持管理员配置 Logo、色板、站点文案、主题和多语言基础。

## Requirements

- 站点名称、Logo、Favicon、主色等可后台配置。
- 前端文案接入 i18n key，不再散落硬编码。
- 支持站点文本覆盖和邮件模板文案覆盖。
- 主题配置可安全预览和回滚。

## Acceptance Criteria

- [ ] 管理员修改品牌后刷新生效。
- [ ] 缺失 i18n key 有 fallback。
- [ ] 普通用户不能修改主题配置。
- [ ] 测试覆盖设置读取。

## Priority

- `P1`：Discourse parity roadmap 中的排期优先级。

## Technical Notes

Discourse 有 site_texts/theme/color_palette。

## Relevant Context

- Parent roadmap: `.trellis/tasks/05-20-discourse-parity-roadmap`
- Source comparison: `D:\work\ParallelLines` vs `D:\work\discourse`
- Implement with project specs under `.trellis/spec/` and update specs when contracts change.
