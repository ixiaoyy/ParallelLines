# 拆分首页大文件

## Goal
把首页 `HomePage.vue` / `HomePage.scss` 拆成小型、可维护的页面展示组件，避免继续形成超大单文件。

## Requirements
- 首页保持现有视觉、真实 API 数据和交互行为不变。
- 抽取左栏、Hero、分类、主题流、右侧栏等展示区块为具名组件，并为每个非平凡组件共置 SCSS。
- `HomePage.vue` 只保留查询、派生数据、URL/搜索/滚动状态协调和组件组装。
- `HomePage.scss` 只保留页面级网格/响应式组合样式，避免上千行样式集中堆叠。
- 不引入静态假数据，不直接调用 fetch/axios。

## Acceptance Criteria
- [ ] 首页功能和数据仍来自 `useBoards` / `useTopicFeed` / `useTags`。
- [ ] 原有主题链接、搜索、tab 切换、加载更多、左右栏入口可用。
- [ ] 首页大文件明显拆分，新增组件单文件尺寸可控。
- [ ] lint、typecheck、build 通过；smoke 流程仍通过。
