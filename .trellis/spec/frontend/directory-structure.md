# Frontend Directory Structure

Target root: `apps/web`.

```text
apps/web/
  src/
    app/                    # app bootstrap, router, providers, layouts
    pages/                  # route-level pages only
      home/
      board/
      topic/
      user/
      admin/
    features/               # user-facing feature modules
      boards/
      topics/
      posts/
      notifications/
      moderation/
    entities/               # domain model display helpers and types
      board/
      topic/
      post/
      user/
    shared/
      api/                  # generated client wrapper and query keys
      ui/                   # design-system primitives
      lib/                  # pure utilities
      styles/               # SCSS tokens, reset, global styles
      assets/
```

## Rules

- Route files belong in `pages`; reusable domain UI belongs in `features` or `entities`.
- Low-level visual primitives belong in `shared/ui` and must not import feature code.
- API calls go through `shared/api` wrappers and query composables.
- Keep feature modules independently understandable: `api.ts`, `queries.ts`, `components/`, `model.ts` when needed.
- Co-locate non-trivial component/page styles as `ComponentName.scss` beside `ComponentName.vue`, then import with `<style scoped lang="scss" src="./ComponentName.scss"></style>`.

## Anti-patterns

- Do not put all components in a single global `components` directory.
- Do not call `fetch`/`axios` directly from arbitrary components.
- Do not create cross-feature circular imports.
