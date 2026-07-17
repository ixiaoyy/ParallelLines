# Type Safety

## Compiler Contract

`apps/web/tsconfig.json` enables strict TypeScript, isolated modules, and no
emit. Keep new code compatible with `vue-tsc -b`; do not weaken compiler options
or suppress a local mismatch globally.

## Type Ownership

- Feature request and response contracts live in the owning feature's `model.ts`
  or, for simple endpoint-only requests, beside `api.ts`.
- Reusable UI-facing models live in `entities/`. Keep transport field names out
  of reusable components.
- Map snake_case API responses to camelCase view models in an explicit mapper.
  `features/topics/model.ts::toTopicCard` and `toPollVM` are the references.
- Small component-only interfaces stay in the component, such as
  `AdminNavigationItem` in `AdminConsoleShell.vue`.
- Use string unions for finite application states and permissions rather than
  free-form strings when the backend contract is closed.

## API Compatibility

HTTP helpers are generic over response and request types. Endpoint functions
must state their `Promise<Response>` result and payload type, as in
`features/admin/api.ts`.

Generated OpenAPI types live in `shared/api/generated.ts`.
`shared/api/contracts.ts` uses compile-time assertions to keep important manual
models assignable to generated schemas. When a covered API contract changes:

1. update the backend schema and manual frontend model deliberately;
2. regenerate or check the OpenAPI output;
3. update `ApiContractChecks` when a newly important contract needs coverage.

Do not edit `generated.ts` by hand.

## Narrowing Untrusted Values

There is no general runtime-schema library in the package. Validate untrusted
browser or stream data with focused type guards:

- `features/admin/publicSettingsCache.ts` narrows cached JSON through `isRecord`.
- `shared/theme/interfaceTheme.ts` validates persisted string values against a
  supported set.
- Notification stream parsing treats decoded JSON as `unknown` before parsing
  its event shape.

Use `unknown` at an untrusted boundary and narrow it. Type assertions are
acceptable only after a concrete invariant has been established or at a typed
platform boundary.

## Useful Local Patterns

- `as const` for stable query-key tuples and immutable configuration arrays.
- `satisfies` when checking an inferred object while preserving its narrow type;
  `features/boards/queries.ts` uses it for `BoardDetailVM`.
- `MaybeRefOrGetter<T>` plus `toValue` for reactive composable parameters.
- `Record<string, unknown>` for an object whose fields still require inspection.
- `Record<string, never>` for an intentionally empty JSON request body.

## Avoid

- `any`, double assertions, or casts used to silence API mismatches.
- Casting route params instead of normalizing them.
- Passing raw response objects directly to components that expect a view model.
- Treating localStorage, JSON parsing, SSE payloads, or user input as already
  typed.
- Duplicating a response interface in a page or component.
