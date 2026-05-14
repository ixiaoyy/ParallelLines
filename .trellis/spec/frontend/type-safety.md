# Frontend Type Safety

## Rules

- Use TypeScript strict mode.
- Prefer generated OpenAPI types for API DTOs.
- Define UI-only derived types in the owning feature/entity module.
- Use discriminated unions for notification types, moderation states, and topic status.
- Runtime validation is required for local storage parsing and external event payloads.

## Naming

- API DTOs: `TopicResponse`, `CreateTopicRequest` from generated client.
- UI models: `TopicCardVM`, `PostItemVM`.
- Status constants use string literal unions: `'open' | 'closed' | 'archived' | 'hidden'`.

## Anti-patterns

- No `any` except at a clearly documented integration boundary.
- No manually duplicated API response types when generated types exist.
- No broad type assertions to silence real nullability issues.
