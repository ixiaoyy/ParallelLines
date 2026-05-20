# 上传、头像与附件存储

## Goal

补齐图片/文件上传、头像上传、附件引用、存储清理与 CDN/S3 兼容能力。

## Requirements

- 支持主题/回复中的图片与文件上传，返回可安全引用的 URL 和元数据。
- 支持用户头像上传、裁剪/校验和默认头像回退。
- 限制文件类型、大小、数量，阻止脚本/可执行文件和伪装 MIME。
- 附件与帖子建立引用关系，删除/隐藏内容时不泄露私有附件。
- 提供本地存储 MVP，并预留 S3/CDN 配置接口。
- 后台任务可清理未引用临时文件和过期上传。

## Acceptance Criteria

- [ ] 登录用户可上传图片并插入发帖正文，刷新后仍可展示。
- [ ] 头像上传后当前用户、作者卡片和用户页一致更新。
- [ ] 非法类型/超限文件返回项目统一错误形态。
- [ ] 未授权用户不能读取私密版块附件。
- [ ] 后端测试覆盖 MIME、大小、引用关系和权限边界。

## Priority

- `P0`：Discourse parity roadmap 中的排期优先级。

## Technical Notes

参考 Discourse uploads/optimized_image/external_upload 方向；优先实现安全上传边界。

## Relevant Context

- Parent roadmap: `.trellis/tasks/05-20-discourse-parity-roadmap`
- Source comparison: `D:\work\ParallelLines` vs `D:\work\discourse`
- Implement with project specs under `.trellis/spec/` and update specs when contracts change.
