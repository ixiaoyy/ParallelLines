# 后台任务队列、重试与定时调度

## Goal

建立可靠后台任务体系，承载邮件、通知、索引、清理、备份和统计等异步工作。

## Requirements

- 定义任务模型或队列适配层，支持 enqueue、retry、dead-letter、幂等键。
- 支持定时任务：热榜刷新、邮件摘要、临时文件清理、会话清理。
- 任务执行日志可查询，失败有可观测性。
- 请求路径中避免长耗时同步工作。
- 本地开发可用简化 worker，生产可切换 Redis/RQ/Celery/Arq。

## Acceptance Criteria

- [ ] 邮件发送和通知 fan-out 可通过后台任务异步执行。
- [ ] 失败任务按策略重试并记录最终状态。
- [ ] 重复 enqueue 同一幂等键不会重复副作用。
- [ ] 测试覆盖成功、失败、重试、幂等。

## Priority

- `P0`：Discourse parity roadmap 中的排期优先级。

## Technical Notes

当前仅有 hot_ranking worker，需扩展为统一 infra。

## Relevant Context

- Parent roadmap: `.trellis/tasks/05-20-discourse-parity-roadmap`
- Source comparison: `D:\work\ParallelLines` vs `D:\work\discourse`
- Implement with project specs under `.trellis/spec/` and update specs when contracts change.
