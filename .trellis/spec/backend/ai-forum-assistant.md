# AI Forum Assistant Backend Contract

## Scope / Trigger

Applies when changing local AI-style summaries, similar-topic recommendations, or moderation advice endpoints.

## Signatures

- `GET /api/v1/topics/{topic_id}/ai-summary` returns cached topic summary or empty state.
- `POST /api/v1/topics/{topic_id}/ai-summary/refresh` regenerates deterministic summary and writes audit/cost metadata.
- `POST /api/v1/ai/similar-topics` returns public similar topics by token overlap.
- `POST /api/v1/ai/moderation-advice` returns risk summary and suggested human-review actions.

## Contracts

- First implementation is deterministic/local; do not call external AI/network from request paths.
- Summaries store `key_points`, `key_post_ids`, `model_name`, `cost_units`, and actor metadata in `ai_topic_summaries`.
- Similar-topic search must respect public visibility and not leak private-message/private-board content.
- Moderation advice never applies automatic moderation actions; `auto_action_allowed=false` and human review is required.

## Validation Matrix

| Case | Expected |
|---|---|
| Missing topic | `topic_not_found`. |
| Refresh by logged-in user | Summary row is upserted and returned. |
| High-risk moderation input | Advice includes risk reasons and review action. |

## Tests

Downgraded roadmap scope: `pytest tests/test_ai_assistant.py -q` plus focused ruff.
