# AI Forum Assistant Frontend Contract

## Scope / Trigger

Applies when changing topic AI summary cards, similar-topic hints, or moderation advice UI wiring.

## Contracts

- Topic details may render `TopicAiSummaryCard`; it must handle empty, loading, error, and refresh states.
- New-topic form may render `SimilarTopicHints`; requests are user-triggered and should not spam on every keystroke.
- AI outputs are advisory copy only; moderation advice must not expose one-click destructive auto-actions.
- Query keys must include topic id or request body hash inputs so cached results do not bleed between topics.

## Validation

Downgraded roadmap scope: frontend `typecheck` + `lint`; backend focused AI test remains source of API truth.
