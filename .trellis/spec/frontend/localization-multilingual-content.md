# Localization and Multilingual Content Frontend Contract

## Scope / Trigger

Applies when changing app locale selection, site text overrides, or localized topic/board display.

## Contracts

- Locale state lives in `shared/i18n/locale.ts` and persists to `localStorage` key `parallellines.locale`.
- App shell text resolves through `siteText(response, key, fallback, locale)` with locale-specific override keys like `en-US.nav.home`, then generic key, then built-in fallback.
- Topic and board view models call `localizedText(localizations, fallback)` before rendering user-facing titles/names.
- Missing translations must fallback to default Chinese copy without blank labels.
- Keep supported locale list explicit until backend user preference sync is added.

## Validation

Downgraded roadmap scope: frontend `typecheck` + `lint`; manual shell language-toggle smoke if practical.
