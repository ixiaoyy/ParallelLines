# 富文本编辑器、Onebox、表情与代码体验

## Goal

升级发帖/回复体验：拖拽上传、预览、链接展开、表情、代码高亮和引用体验。

## Requirements

- 编辑器支持 Markdown 快捷工具栏、实时预览和草稿状态。
- 拖拽上传图片并插入 Markdown。
- 链接 onebox 展开标题/摘要/图片。
- 支持自定义表情和代码高亮语言选择。

## Acceptance Criteria

- [ ] 用户可拖图发帖且预览一致。
- [ ] URL 自动展开但可安全降级。
- [ ] 代码块复制/高亮稳定。
- [ ] 前端 smoke 覆盖核心编辑路径。

## Priority

- `P1`：Discourse parity roadmap 中的排期优先级。

## Technical Notes

依赖 uploads；Onebox 后端需安全抓取超时。

## Relevant Context

- Parent roadmap: `.trellis/tasks/05-20-discourse-parity-roadmap`
- Source comparison: `D:\work\ParallelLines` vs `D:\work\discourse`
- Implement with project specs under `.trellis/spec/` and update specs when contracts change.
