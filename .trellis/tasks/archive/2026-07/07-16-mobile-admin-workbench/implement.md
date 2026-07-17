# 实施计划

## 实现

- [x] 在 `AdminWorkbenchPanel.vue` 增加短日期展示，不改变查询、指标或路由。
- [x] 在 `AdminWorkbenchPanel.scss` 将手机摘要与骨架调整为 2×2，并压缩页头、区块、健康态和快捷入口节奏。
- [x] 在 `AdminConsoleShell.scss` 优化移动顶栏、底栏、安全区、极窄屏文案和触控尺寸。
- [x] 检查 `AdminConsoleShell.vue` 现有权限过滤、抽屉焦点和导航项映射无需行为改动。
- [x] 增加 `admin-workbench-responsive.spec.ts`，用稳定假数据覆盖常见响应式视口。

## 验证

- [x] `git diff --check`
- [x] `pnpm typecheck:web`
- [x] 运行定向 Playwright 响应式用例。
- [x] 检查 320px、390px、860px 和 1440px 截图与溢出断言。
- [x] 确认 Logo/favicon、API、权限、路由和统计代码没有变更。

## 风险点

- `680px` 内容断点与 `860px` 控制台断点职责必须分离。
- 六项底部导航在 320px 下仍需满足触控宽度；不能通过隐藏入口解决拥挤。
- 固定底栏与 iOS safe area 的高度必须同时计入页面占位。
- 现有工作区包含其他未提交改动；只处理并提交本任务及 Trellis 规范文件。
