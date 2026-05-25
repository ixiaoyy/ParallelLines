# Frontend OpenAPI Generated Types Contract

## Scenario: generated DTO types catch backend/frontend drift

### 1. Scope / Trigger

- Trigger: changing generated API types, frontend DTO contracts, API client wrappers, or CI type
  generation checks.
- Applies to `apps/web/scripts/generate-openapi-types.mjs`,
  `src/shared/api/generated.ts`, `src/shared/api/contracts.ts`, feature `model.ts` DTOs,
  `package.json`, and CI.

### 2. Signatures

Frontend commands:

```bash
pnpm --dir apps/web openapi:types
pnpm --dir apps/web openapi:check
```

Generated files:

- Source schema: `apps/api/openapi/openapi.json`.
- Generated TS: `apps/web/src/shared/api/generated.ts`.
- Compile-time contract checks: `apps/web/src/shared/api/contracts.ts`.

### 3. Contracts

- `generated.ts` is generated only from the committed OpenAPI snapshot and must not be edited by
  hand.
- `openapi:check` must fail when `generated.ts` is stale.
- Manual feature DTOs may remain during gradual migration, but `contracts.ts` must assert that core
  DTOs extend generated schemas so required backend field drift fails `vue-tsc`.
- Feature modules continue to call `shared/api/client.ts`; generated types are a type boundary, not
  a reason to bypass existing API wrappers/query composables.
- CI frontend job must run `openapi:check` before `typecheck`.

### 4. Validation & Error Matrix

| Case | Expected behavior |
|---|---|
| Backend adds required `TopicResponse` field | regenerate OpenAPI/types; if manual DTO is stale, `typecheck` fails |
| Generated file edited by hand | `openapi:check` fails |
| API wrapper bypassed in component | frontend lint/spec review rejects direct fetch |
| Optional response field added | generated type updates; existing manual DTOs may remain compatible |

### 5. Good/Base/Bad Cases

- Good: `TopicResponse.share_url` is required by OpenAPI; manual `TopicResponse` marks it required
  and mapper uses it directly.
- Base: generated `components["schemas"]` types coexist with handwritten view-model mappers.
- Bad: copying OpenAPI schema fields into feature models without a compile-time compatibility check.

### 6. Tests Required

Downgraded roadmap scope:

- `pnpm --dir apps/web openapi:check`
- `pnpm --dir apps/web typecheck`
- `pnpm --dir apps/web lint`

### 7. Wrong vs Correct

#### Wrong

```ts
export interface TopicResponse { share_url?: string }
```

#### Correct

```ts
export interface TopicResponse { share_url: string }
// contracts.ts also asserts TopicResponse extends generated TopicResponse.
```
