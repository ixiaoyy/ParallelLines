# 修复帖子详情页 UI 与路由

## Goal
修复帖子详情页当前严重的视觉/布局问题，并理顺主题详情路由，避免页面实现继续膨胀成单文件堆叠。

## Requirements
- 调整帖子详情页桌面与窄屏布局，使标题、统计、楼层、侧栏、回复区密度合理且不出现截图中的巨大留白/过宽标题/内容挤压。
- 修正主题详情路由与链接生成，使用一致、可读、可分享的主题 URL，并兼容现有入口。
- 遵守前端目录与组件规范：路由页只负责组装和状态协调，非平凡 UI 拆到 feature/topic 或 post 组件及共置 SCSS。
- 不引入静态假数据，不绕过现有 TanStack Query/API wiring。
- 保持发帖、回复、复制链接、只看楼主、引用、举报等既有行为可用。

## Acceptance Criteria
- [ ] 帖子详情页视觉层级清晰，主内容宽度、侧栏、卡片、正文排版在桌面截图尺寸下正常。
- [ ] 窄屏下布局单列，侧栏和操作区不挤压内容。
- [ ] 主题详情链接/跳转统一，老链接仍可打开或自动规整。
- [ ] TopicDetailPage.vue 不再承担大量展示结构，拆分为可复用小组件。
- [ ] lint、typecheck、build 通过。

## Technical Notes
- 前端栈：Vue 3 + Vite + TypeScript + Vue Router + TanStack Query + SCSS。
- 重点遵守 `.trellis/spec/frontend/directory-structure.md`、`component-guidelines.md`、`forum-api-wiring.md`、`post-actions.md`、`quality-guidelines.md`。
