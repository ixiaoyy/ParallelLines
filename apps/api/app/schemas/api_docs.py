from pydantic import BaseModel, Field


class PublicApiExample(BaseModel):
    title: str
    request: dict[str, object]
    response: dict[str, object]


class PublicApiDocsResponse(BaseModel):
    api_version: str
    openapi_url: str
    authentication: dict[str, str]
    pagination: dict[str, object]
    error_shape: dict[str, object]
    compatibility_policy: dict[str, object]
    examples: list[PublicApiExample] = Field(default_factory=list)
