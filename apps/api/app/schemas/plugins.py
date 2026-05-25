from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

PluginEventName = Literal["topic.created", "post.created", "user.created"]
PluginSlotName = Literal["app.nav", "topic.sidebar", "home.sidebar"]


class PluginUiExtensionResponse(BaseModel):
    plugin_id: str
    slot: str
    key: str
    title: str
    description: str
    component: str
    props: dict[str, object] = Field(default_factory=dict)


class PluginResponse(BaseModel):
    id: str
    name: str
    description: str
    version: str
    enabled: bool
    events: list[str]
    ui_extensions: list[PluginUiExtensionResponse]
    config: dict[str, object] = Field(default_factory=dict)


class PluginUpdateRequest(BaseModel):
    enabled: bool
    config: dict[str, object] = Field(default_factory=dict)


class PluginEventResultResponse(BaseModel):
    plugin_id: str
    event: str
    ok: bool
    error: str | None = None
