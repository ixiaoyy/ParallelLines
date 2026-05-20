# SEO、永久链接、Sitemap 与分享元数据

## Goal

补齐公开论坛可被搜索引擎和社交平台正确索引/分享的能力。

## Requirements

- 生成 sitemap.xml 和 robots.txt。
- 主题/版块/用户页提供规范 canonical URL。
- 支持 permalink/旧 URL 跳转。
- 公开页面输出 OpenGraph/Twitter card 元数据。

## Acceptance Criteria

- [ ] 隐藏/私密内容不进入 sitemap。
- [ ] 旧链接可 301/302 到新主题。
- [ ] 分享预览显示标题摘要。
- [ ] 测试覆盖私密过滤。

## Priority

- `P1`：Discourse parity roadmap 中的排期优先级。

## Technical Notes

当前 SPA 可能需 SSR/预渲染或后端 metadata 接口。

## Relevant Context

- Parent roadmap: `.trellis/tasks/05-20-discourse-parity-roadmap`
- Source comparison: `D:\work\ParallelLines` vs `D:\work\discourse`
- Implement with project specs under `.trellis/spec/` and update specs when contracts change.
