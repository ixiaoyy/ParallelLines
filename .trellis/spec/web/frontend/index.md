# ParallelLines Web Frontend Guidelines

The web package is a Vue 3, TypeScript, Vite application under `apps/web`. It uses
feature-oriented modules, TanStack Vue Query for server state, Ant Design Vue plus
project-owned UI wrappers, and SCSS design tokens.

## Guidelines Index

| Guide | Use it for |
|---|---|
| [Directory Structure](./directory-structure.md) | Choosing the owning layer and file location |
| [Component Guidelines](./component-guidelines.md) | Vue component composition, props, events, and accessibility |
| [Composable Guidelines](./composable-guidelines.md) | Reusable reactive logic and Vue Query hooks |
| [State Management](./state-management.md) | Local, URL, server, auth, and persisted browser state |
| [Type Safety](./type-safety.md) | API contracts, view models, narrowing, and strict TypeScript |
| [Styling Guidelines](./styling-guidelines.md) | Tokens, responsive CSS, brand rules, and scoped styles |
| [Quality Guidelines](./quality-guidelines.md) | Validation commands and review gates |

## Pre-Development Checklist

1. Read [Directory Structure](./directory-structure.md) before adding or moving a
   module.
2. For Vue or SCSS work, read [Component Guidelines](./component-guidelines.md)
   and [Styling Guidelines](./styling-guidelines.md).
3. For API, cache, or reactive-state work, read
   [Composable Guidelines](./composable-guidelines.md),
   [State Management](./state-management.md), and
   [Type Safety](./type-safety.md).
4. Search for an existing UI component, query key, mapper, token, or helper before
   creating another one.
5. Preserve the protected logo paths and the `#409EFF` primary-button contract in
   the repository `AGENTS.md`.

## Quality Check

Follow [Quality Guidelines](./quality-guidelines.md). At minimum, inspect the
final diff and run `pnpm typecheck:web` for application-code changes. Add lint,
OpenAPI checks, builds, or Playwright smoke coverage only when the changed
surface requires them.
