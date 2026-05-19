# PRD: Architecture and Domain Baseline

## Goal

Finalize product architecture before code implementation. Convert the Discourse-inspired concepts into concrete domain rules, API conventions, permissions, and data contracts.

## Deliverables

- Update `.trellis/spec/product/discourse-inspired-parallellines-design.md` when scope changes.
- Define canonical domain vocabulary: Board, Topic, Post, Tag, TopicRead, Notification, Flag, AuditLog.
- Define API response envelope, error shape, pagination strategy, and auth strategy.
- Define role and permission matrix for visitor/user/moderator/admin.

## Acceptance Criteria

- Every MVP feature maps to at least one domain entity and endpoint.
- Cross-layer data flow for creating a topic and posting a reply is documented.
- Security boundaries are explicit: content sanitization, rate limit, soft delete, authorization.
- Later implementation tasks can proceed without redefining domain vocabulary.
