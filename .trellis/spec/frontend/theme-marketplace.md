# Theme Marketplace Frontend Contract

## Scope / Trigger

Applies when changing built-in theme packages, admin theme marketplace preview/enable/rollback, or theme validation.

## Contracts

- Theme package definitions live in `features/themes/model.ts`; validation rejects scripts, unsafe asset URLs, and invalid hex colors.
- Admin UI may preview browser-local theme variables without saving.
- Enabling a theme persists only whitelisted public setting keys through `useUpdateAdminSetting`.
- Rollback reapplies server public site settings via `applySiteBranding`.
- Do not execute arbitrary theme JavaScript; theme components are registry/slot metadata only in this phase.

## Validation

Downgraded roadmap scope: frontend `typecheck` + `lint`; manual `/admin` preview/rollback smoke if practical.
