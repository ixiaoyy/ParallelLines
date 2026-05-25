# Localization and Multilingual Content Backend Contract

## Scope / Trigger

Applies when changing locale preferences, topic/board localizable fields, or content localization APIs.

## Signatures

- `PUT /api/v1/topics/{topic_id}/localizations/{locale}` upserts/removes a localized topic title.
- `GET /api/v1/topics/{topic_id}/localizations/{locale}` resolves localized title with fallback.
- `TopicResponse.title_localizations` and `BoardResponse.name_localizations` expose safe localization maps.

## Contracts

- Locale must look like BCP47-style `zh-CN` or `en-US`; `_` is normalized to `-`.
- Topic localization updates require admin, global moderator, board owner, or board moderator.
- Missing exact locale falls back to language-only key, then default title/name.
- Updating localization writes `topic_localization_updated` audit log.
- Search/SEO remain default-language first in this phase; localized indexing can be added later.

## Validation Matrix

| Case | Expected |
|---|---|
| `en_US` lookup | Normalized to `en-US`. |
| Missing translation | Default title returned with `fallback_used=true`. |
| Non-moderator update | `content_localization_forbidden` / 403. |
| Empty title update | Locale key removed. |

## Tests

Downgraded roadmap scope: `pytest tests/test_localization.py -q` plus focused ruff.
