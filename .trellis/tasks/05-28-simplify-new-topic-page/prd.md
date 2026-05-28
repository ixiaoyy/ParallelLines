# 简化发帖页面

## Goal

把 `/new-topic` 从分步骤讲解式表单改成接近 Discourse 的轻量发布框：少说明、少卡片、直接选择版块/标签，填写标题和正文后发布。

## Requirements

- 保留现有发帖 API、草稿保存、上传插入和版块必填/允许标签校验。
- 移除冗长的步骤导航、意图选择、预览检查、投票配置和侧边说明。
- 版块选择、标签输入、标题、正文和发布按钮集中在一个表单中。
- 标签策略只在必要时用短提示/芯片展示，不能像流程说明一样占大面积。
- 不改变主按钮配色规范。

## Acceptance Criteria

- 用户进入 `/new-topic` 后可在首屏完成标题、版块、标签、正文和发布。
- 非必填标签的版块不强制用户补标签。
- 版块必填标签可一键补齐或自动补齐，后端仍为最终校验。
- `pnpm lint:web`、`pnpm typecheck:web`、`pnpm build:web` 通过。

## Technical Notes

- 主要修改 `apps/web/src/pages/topic/NewTopicPage.vue` 和同目录 SCSS。
- 保留 `MarkdownUploadButton`、`useSaveDraft`、`useDeleteDraft`、`lookupDraft`。
