from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.core.permissions import is_admin
from app.db.base import utcnow
from app.models.admin import SiteSetting
from app.models.moderation import AuditLog
from app.models.user import User
from app.schemas.plugins import (
    PluginEventResultResponse,
    PluginResponse,
    PluginUiExtensionResponse,
    PluginUpdateRequest,
)

PLUGIN_CONFIG_SETTING_KEY = "plugins_config"
PluginHandler = Callable[[AsyncSession, dict[str, object]], Awaitable[dict[str, object] | None]]


@dataclass(frozen=True)
class PluginUiExtension:
    slot: str
    key: str
    title: str
    description: str
    component: str
    props: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class PluginDefinition:
    id: str
    name: str
    description: str
    version: str
    events: tuple[str, ...]
    ui_extensions: tuple[PluginUiExtension, ...]
    handlers: dict[str, PluginHandler] = field(default_factory=dict)


async def example_topic_created_handler(
    session: AsyncSession,
    payload: dict[str, object],
) -> dict[str, object]:
    topic_id = str(payload.get("topic_id") or "")
    session.add(
        AuditLog(
            actor_id=str(payload.get("author_id") or "") or None,
            action="plugin_example_topic_created",
            target_type="plugin",
            target_id="example-topic-tools",
            board_id=str(payload.get("board_id") or "") or None,
            data={"topic_id": topic_id, "title": str(payload.get("title") or "")[:180]},
            created_at=utcnow(),
        )
    )
    return {"topic_id": topic_id}


PLUGIN_REGISTRY: dict[str, PluginDefinition] = {
    "example-topic-tools": PluginDefinition(
        id="example-topic-tools",
        name="示例主题工具",
        description="演示事件 hook 与前端导航扩展入口。",
        version="0.1.0",
        events=("topic.created",),
        ui_extensions=(
            PluginUiExtension(
                slot="app.nav",
                key="example-topic-tools-nav",
                title="插件示例",
                description="一个由插件注册的安全导航入口。",
                component="link-card",
                props={"href": "/search?q=plugin", "label": "插件示例"},
            ),
        ),
        handlers={"topic.created": example_topic_created_handler},
    ),
    "broken-example": PluginDefinition(
        id="broken-example",
        name="异常隔离示例",
        description="用于验证插件异常不会拖垮核心请求。",
        version="0.1.0",
        events=("topic.created",),
        ui_extensions=(),
        handlers={"topic.created": lambda _session, _payload: _raise_plugin_error()},
    ),
}


async def _raise_plugin_error() -> dict[str, object]:
    raise RuntimeError("example plugin failure")


class PluginService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_plugins(self, current_user: User) -> list[PluginResponse]:
        self._require_admin(current_user)
        config = await self._plugin_config()
        return [self._response(definition, config) for definition in PLUGIN_REGISTRY.values()]

    async def update_plugin(
        self,
        plugin_id: str,
        payload: PluginUpdateRequest,
        current_user: User,
    ) -> PluginResponse:
        self._require_admin(current_user)
        definition = self._require_plugin(plugin_id)
        config = await self._plugin_config()
        config[plugin_id] = {"enabled": payload.enabled, "config": payload.config}
        setting = await self._config_setting()
        setting.value = config
        setting.updated_by_id = current_user.id
        self._add_audit_log(
            actor_id=current_user.id,
            action="plugin_config_updated",
            target_id=plugin_id,
            data={"enabled": payload.enabled, "config_keys": sorted(payload.config.keys())},
        )
        await self.session.commit()
        return self._response(definition, config)

    async def public_ui_extensions(self) -> list[PluginUiExtensionResponse]:
        config = await self._plugin_config()
        extensions: list[PluginUiExtensionResponse] = []
        for definition in PLUGIN_REGISTRY.values():
            if not self._enabled(definition.id, config):
                continue
            extensions.extend(self._ui_extensions(definition))
        return extensions

    async def emit_event(
        self,
        event: str,
        payload: dict[str, object],
    ) -> list[PluginEventResultResponse]:
        config = await self._plugin_config()
        results: list[PluginEventResultResponse] = []
        for definition in PLUGIN_REGISTRY.values():
            if not self._enabled(definition.id, config) or event not in definition.events:
                continue
            handler = definition.handlers.get(event)
            if handler is None:
                continue
            try:
                await handler(self.session, payload)
                results.append(
                    PluginEventResultResponse(plugin_id=definition.id, event=event, ok=True)
                )
            except Exception as exc:  # noqa: BLE001 - plugin boundary must isolate all failures.
                message = (str(exc) or type(exc).__name__)[:500]
                self._add_audit_log(
                    actor_id=None,
                    action="plugin_hook_failed",
                    target_id=definition.id,
                    data={"event": event, "error": message},
                )
                results.append(
                    PluginEventResultResponse(
                        plugin_id=definition.id,
                        event=event,
                        ok=False,
                        error=message,
                    )
                )
        return results

    async def _plugin_config(self) -> dict[str, dict[str, Any]]:
        setting = await self._config_setting()
        if not isinstance(setting.value, dict):
            setting.value = {}
        return dict(setting.value)

    async def _config_setting(self) -> SiteSetting:
        setting = await self.session.scalar(
            select(SiteSetting).where(SiteSetting.key == PLUGIN_CONFIG_SETTING_KEY)
        )
        if setting is not None:
            return setting
        setting = SiteSetting(
            key=PLUGIN_CONFIG_SETTING_KEY,
            value={},
            data_type="json",
            category="plugins",
            description="插件启停与插件配置，格式为 plugin_id 到配置对象的映射。",
            public=False,
        )
        self.session.add(setting)
        await self.session.flush()
        return setting

    def _response(
        self,
        definition: PluginDefinition,
        config: dict[str, dict[str, Any]],
    ) -> PluginResponse:
        plugin_config = self._definition_config(definition.id, config)
        return PluginResponse(
            id=definition.id,
            name=definition.name,
            description=definition.description,
            version=definition.version,
            enabled=self._enabled(definition.id, config),
            events=list(definition.events),
            ui_extensions=self._ui_extensions(definition),
            config=dict(plugin_config.get("config") or {}),
        )

    def _ui_extensions(self, definition: PluginDefinition) -> list[PluginUiExtensionResponse]:
        return [
            PluginUiExtensionResponse(
                plugin_id=definition.id,
                slot=extension.slot,
                key=extension.key,
                title=extension.title,
                description=extension.description,
                component=extension.component,
                props=extension.props,
            )
            for extension in definition.ui_extensions
        ]

    def _enabled(self, plugin_id: str, config: dict[str, dict[str, Any]]) -> bool:
        plugin_config = self._definition_config(plugin_id, config)
        return bool(plugin_config.get("enabled", False))

    def _definition_config(
        self,
        plugin_id: str,
        config: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        plugin_config = config.get(plugin_id, {})
        return plugin_config if isinstance(plugin_config, dict) else {}

    def _require_plugin(self, plugin_id: str) -> PluginDefinition:
        plugin = PLUGIN_REGISTRY.get(plugin_id)
        if plugin is None:
            raise NotFoundError("plugin_not_found", "Plugin not found")
        return plugin

    def _require_admin(self, current_user: User) -> None:
        if not is_admin(current_user):
            raise PermissionDeniedError("admin_required", "Admin role required")

    def _add_audit_log(
        self,
        *,
        actor_id: str | None,
        action: str,
        target_id: str,
        data: dict[str, object],
    ) -> None:
        self.session.add(
            AuditLog(
                actor_id=actor_id,
                action=action,
                target_type="plugin",
                target_id=target_id,
                board_id=None,
                data=data,
                created_at=utcnow(),
            )
        )
