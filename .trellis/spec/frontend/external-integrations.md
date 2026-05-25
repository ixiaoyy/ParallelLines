# External Integrations Frontend Contract

## Scope / Trigger

Applies when changing admin external provider UI or GitHub issue preview UI/data wiring.

## Contracts

- Admin external integrations UI lives under `features/external-integrations/` and is mounted on `/admin`.
- Provider config edits use feature API/query helpers, not direct component fetch calls.
- Secret fields (`webhook_secret`, tokens) are displayed redacted after save and must not be echoed from forms unless the admin re-enters them.
- Event retry buttons disable when pending or retry count reached `max_retries`.
- GitHub issue previews use `queryKeys.githubIssuePreview(url)` so onebox/cache behavior is stable.

## Validation

Downgraded roadmap scope: frontend `typecheck` + `lint`; manual admin smoke if practical.
