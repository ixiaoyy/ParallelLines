# 实时 Chat、在线状态与 Presence

## Goal

实现论坛内即时聊天、在线用户、输入状态和实时频道。

## Requirements

- 支持私聊/频道聊天消息。
- 显示在线状态和正在输入。
- 消息权限遵循版块/群组。
- 历史消息分页和搜索。

## Acceptance Criteria

- [ ] 用户可在频道发送/接收实时消息。
- [ ] 无权限用户不能进入私有频道。
- [ ] 断线重连后消息不丢。

## Priority

- `P2`：Discourse parity roadmap 中的排期优先级。

## Technical Notes

可基于 SSE/WebSocket；对应 discourse-chat/presence。

## Relevant Context

- Parent roadmap: `.trellis/tasks/05-20-discourse-parity-roadmap`
- Source comparison: `D:\work\ParallelLines` vs `D:\work\discourse`
- Implement with project specs under `.trellis/spec/` and update specs when contracts change.
