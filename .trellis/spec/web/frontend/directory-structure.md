# Directory Structure

## Layer Ownership

`apps/web/src` has five stable top-level areas:

```text
src/
├── app/       # application bootstrapping, router, and app-wide layouts
├── pages/     # route entry components
├── features/  # business capabilities, API calls, queries, and feature UI
├── entities/  # reusable UI-facing domain models
└── shared/    # generic API, UI, theme, router, formatting, and browser utilities
```

- `main.ts` installs Vue Query, Pinia, the router, global styles, theme state, and
  PWA registration.
- `app/router.ts` owns route definitions, lazy page loading, access metadata, and
  the route guard.
- A page should compose access/loading state and feature panels. For example,
  `pages/admin/AdminDashboardPage.vue` gates access and renders
  `features/admin/components/AdminWorkbenchPanel.vue`.
- A feature normally owns `api.ts`, `model.ts`, `queries.ts`, and an optional
  `components/` directory. `features/boards/` and `features/admin/` are the main
  references.
- `entities/` holds UI-facing models reused across features. API response models
  stay in the feature that owns the endpoint; `features/topics/model.ts` maps
  `TopicResponse` to `entities/topic/model.ts`'s `TopicCardVM`.
- `shared/` is for business-neutral infrastructure. Examples include
  `shared/api/client.ts`, `shared/api/queryKeys.ts`, `shared/ui/`, and
  `shared/theme/`.

## Placement Rules

- Put a route shell in `pages/`; do not grow it into a second feature module.
- Put endpoint functions in the owning feature's `api.ts`, reactive query and
  mutation wrappers in `queries.ts`, and request/response types plus mappers in
  `model.ts`.
- Put reusable business UI inside its feature. Promote a component to
  `shared/ui/` only when it is domain-neutral and has multiple consumers.
- Put cross-feature display models in `entities/`, not raw transport contracts.
- Cross-feature imports exist when one feature consumes another feature's public
  model or mapper, such as `features/boards/queries.ts` using
  `features/topics/model.ts`. Keep these imports explicit; do not create barrel
  files merely to hide ownership.
- Use the `@/` alias for imports across directories. Use relative imports for
  files within the same feature, as seen in `features/admin/api.ts` and
  `features/admin/queries.ts`.

## Naming

- Vue components and pages use PascalCase: `TopicCard.vue`,
  `AdminDashboardPage.vue`.
- Reusable reactive functions use `useXxx.ts`: `useMediaQuery.ts`,
  `useOptimisticToggle.ts`.
- Feature infrastructure uses the stable lowercase names `api.ts`, `model.ts`,
  and `queries.ts`.
- Substantial component styles live beside the component with the same basename,
  for example `AdminConsoleShell.vue` and `AdminConsoleShell.scss`.
- Route names use kebab-case strings such as `admin-dashboard`; route component
  files remain PascalCase.

## Avoid

- Do not call the HTTP client directly from templates or scatter endpoint URLs
  across pages.
- Do not place feature-specific types or copy in `shared/`.
- Do not duplicate route-parameter parsing, query keys, formatters, or palette
  logic locally; search `shared/router`, `shared/api`, `shared/lib`, and
  `shared/theme` first.
- Do not introduce a new top-level layer without a repeated ownership problem
  that the existing five areas cannot express.
