# PRD: Frontend Vue Design System

## Goal

Create the Vue 3 application shell and reusable UI system for a polished forum experience.

## Scope

- Vite + Vue 3 + TypeScript + Ant Design Vue project under `apps/web`.
- Vue Router, Pinia, TanStack Query, OpenAPI client wrapper.
- Global CSS reset and tokens using the requested palette.
- Ant Design Vue `ConfigProvider` theme plus wrapped `Button`, `Card`, `Avatar`, `Badge`, `Tabs`, `Skeleton`, `EmptyState`.
- Forum primitives: `TopicCard`, `BoardCard`, `PostItem`, `ComposerDrawer` static/fixture state.
- Responsive layout for desktop three-column and mobile bottom nav.

## Acceptance Criteria

- App renders a fixture-driven home page without backend.
- Color tokens include `#F8F9FA`, `#3B82F6`, `#10B981`, `#111827`, `#4B5563`, `#1E1E1E`.
- Components are typed and accessible.
- No raw API calls outside `shared/api`.
