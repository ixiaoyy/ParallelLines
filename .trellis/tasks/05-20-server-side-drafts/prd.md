# 服务端草稿与多端恢复

## Goal

将当前浏览器本地草稿升级为服务端草稿，支持新主题/回复多设备同步和恢复。

## Requirements

- 草稿按用户、目标类型、目标 ID、草稿类型存储。
- 自动保存需防抖和版本号，避免覆盖较新草稿。
- 发布成功后清理对应草稿。
- 草稿内容不向其他用户泄露。

## Acceptance Criteria

- [ ] 登录用户刷新或换设备后能恢复草稿。
- [ ] 并发保存不会覆盖新版本。
- [ ] 发布成功后草稿消失。
- [ ] 测试覆盖权限和清理。

## Priority

- `P1`：Discourse parity roadmap 中的排期优先级。

## Technical Notes

对应 Discourse drafts/backup_draft。

## Relevant Context

- Parent roadmap: `.trellis/tasks/05-20-discourse-parity-roadmap`
- Source comparison: `D:\work\ParallelLines` vs `D:\work\discourse`
- Implement with project specs under `.trellis/spec/` and update specs when contracts change.
