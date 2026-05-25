import json

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from scripts.export_openapi import DEFAULT_OUTPUT, render_schema, stable_openapi_document


@pytest.mark.asyncio
async def test_public_api_docs_endpoint_and_versioned_openapi() -> None:
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        docs = await client.get("/api/v1/docs/public")
        assert docs.status_code == 200
        payload = docs.json()["data"]
        assert payload["api_version"] == "v1"
        assert payload["openapi_url"] == "/api/v1/openapi.json"
        assert "Authorization: Bearer" in payload["authentication"]["header"]
        assert payload["pagination"]["response_meta"]["next_cursor"]
        assert payload["error_shape"]["error"]["code"] == "validation_error"
        assert payload["compatibility_policy"]["deprecation_window_days"] == 90

        schema = await client.get("/api/v1/openapi.json")
        assert schema.status_code == 200
        schema_payload = schema.json()
        assert schema_payload["info"]["title"] == "ParallelLines"
        assert "Authorization: Bearer" in schema_payload["info"]["description"]
        assert "/api/v1/docs/public" in schema_payload["paths"]


@pytest.mark.asyncio
async def test_openapi_schema_has_auth_errors_and_stable_operation_ids() -> None:
    schema = create_app().openapi()
    security_schemes = schema["components"]["securitySchemes"]
    assert "OAuth2PasswordBearer" in security_schemes
    assert security_schemes["OAuth2PasswordBearer"]["flows"]["password"]["tokenUrl"] == (
        "/api/v1/auth/login"
    )
    assert "ErrorResponse" in schema["components"]["schemas"]

    operation_ids: list[str] = []
    for path_item in schema["paths"].values():
        for method in ("get", "post", "put", "patch", "delete"):
            operation = path_item.get(method)
            if operation:
                operation_ids.append(operation["operationId"])
    assert len(operation_ids) == len(set(operation_ids))


@pytest.mark.asyncio
async def test_openapi_snapshot_is_current() -> None:
    content = render_schema(stable_openapi_document())
    assert DEFAULT_OUTPUT.read_text(encoding="utf-8") == content
    # Stable JSON must be parseable by frontend generators and CI diff tools.
    parsed = json.loads(content)
    assert parsed["info"]["x-schema-source"] == "apps/api/scripts/export_openapi.py"
