# Import, Export, and Migration Tools Frontend Contract

## Scope / Trigger

Applies when changing admin migration JSON preview/run/export UI.

## Contracts

- UI lives under `features/migrations/` and is mounted on `/admin` as `AdminMigrationToolsPanel`.
- Components use feature API/query helpers for `/admin/migrations/*`; do not parse or mutate data in page components.
- Preview and run share the same JSON editor; parse errors must be shown before API calls.
- Run action is visibly distinct from preview and should be treated as destructive/admin-only.
- Export snapshot download must be client-side JSON generated from the redacted API response.

## Validation

Downgraded roadmap scope: frontend `typecheck` + `lint`; backend migration focused test remains API source of truth.
