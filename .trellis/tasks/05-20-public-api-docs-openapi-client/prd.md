# 公开 API 文档、客户端生成与兼容策略

## Goal

将当前内部 API 整理成可维护公开契约，支持 OpenAPI client、版本、弃用和示例。

## Requirements

- OpenAPI schema 稳定输出并覆盖鉴权说明。
- 前端使用生成类型或集中 DTO，避免手写漂移。
- API 版本和弃用策略明确。
- 公开文档包含常见调用示例和错误形态。

## Acceptance Criteria

- [ ] CI 检查 OpenAPI diff 或类型生成。
- [ ] 前后端字段变更能被 typecheck 捕获。
- [ ] 文档展示 auth、pagination、error。
- [ ] 测试覆盖 schema 生成。

## Priority

- `P1`：Discourse parity roadmap 中的排期优先级。

## Technical Notes

现有前端仍有手写模型，可逐步迁移。

## Relevant Context

- Parent roadmap: `.trellis/tasks/05-20-discourse-parity-roadmap`
- Source comparison: `D:\work\ParallelLines` vs `D:\work\discourse`
- Implement with project specs under `.trellis/spec/` and update specs when contracts change.
