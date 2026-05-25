# Backend Public API, OpenAPI, and Compatibility Contract

## Scenario: stable OpenAPI schema, public docs, and CI drift checks

### 1. Scope / Trigger

- Trigger: changing public API shape, auth/error envelope docs, OpenAPI metadata, schema snapshot,
  or CI checks for API compatibility.
- Applies to `app/main.py`, `app/core/openapi_contract.py`, `app/api/v1/api_docs.py`,
  `app/schemas/api_docs.py`, `scripts/export_openapi.py`, `openapi/openapi.json`, CI, and
  `tests/test_public_api_docs.py`.

### 2. Signatures

Public docs APIs:

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `GET` | `/api/v1/openapi.json` | public | Versioned alias for the OpenAPI document. |
| `GET` | `/api/v1/docs/public` | public | Structured docs for auth, pagination, error shape, examples, and compatibility. |

Schema commands:

```bash
uv --directory apps/api run python scripts/export_openapi.py
uv --directory apps/api run python scripts/export_openapi.py --check
```

OpenAPI snapshot path: `apps/api/openapi/openapi.json`.

### 3. Contracts

- FastAPI app metadata must include public API description covering Bearer auth, pagination,
  error shape, and `/api/v1` compatibility policy.
- OpenAPI components must explicitly include `ErrorResponse` so clients can document the standard
  `{ error: { code, message, details } }` shape even when individual routes omit error responses.
- `scripts/export_openapi.py` writes deterministic JSON with sorted keys and `info.x-schema-source`.
- `--check` must fail when the committed snapshot is stale.
- OpenAPI operation IDs must remain unique; endpoint function renames are API-client relevant.
- CI backend job must run the OpenAPI snapshot check after tests.

### 4. Validation & Error Matrix

| Case | Expected behavior |
|---|---|
| Snapshot missing | `export_openapi.py --check` exits non-zero |
| Backend route/schema changed but snapshot not regenerated | `--check` exits non-zero |
| Duplicate operation ID | focused schema test fails |
| Public docs endpoint called anonymously | `200` with auth/pagination/error/compatibility sections |
| Versioned OpenAPI alias called | `200` JSON schema with `/api/v1/*` paths |

### 5. Good/Base/Bad Cases

- Good: backend response model changes; developer runs export script, frontend type generator, and
  CI verifies both snapshots.
- Base: docs endpoint returns examples without requiring DB access.
- Bad: relying only on `/docs` Swagger UI with no committed OpenAPI diff target.
- Bad: changing endpoint function names casually, causing generated client operation IDs to churn.

### 6. Tests Required

Downgraded roadmap scope:

- `ruff check app/core/openapi_contract.py app/schemas/api_docs.py app/api/v1/api_docs.py app/api/v1/router.py app/main.py scripts/export_openapi.py tests/test_public_api_docs.py`
- `pytest tests/test_public_api_docs.py -q`
- `python scripts/export_openapi.py --check`

Assertions: docs endpoint content, versioned schema route, auth security scheme, error component,
unique operation IDs, and committed snapshot freshness.

### 7. Wrong vs Correct

#### Wrong

```bash
curl http://localhost:8000/openapi.json > /tmp/schema.json  # not committed or checked
```

#### Correct

```bash
uv --directory apps/api run python scripts/export_openapi.py --check
```
