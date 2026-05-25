# Plugin Extension System Contract

## Scenario: Safe plugin registry, event hooks, and public UI extension metadata

### 1. Scope / Trigger

- Trigger: adding plugin definitions, backend event hooks, admin plugin enable/disable APIs, or
  public extension metadata consumed by the frontend.
- Applies to `app/services/plugins.py`, `schemas/plugins.py`, `api/v1/admin.py`,
  `api/v1/site.py`, and core service emit points such as `ForumService.create_topic()`.

### 2. Signatures

Backend endpoints:

| Endpoint | Auth | Purpose |
|---|---|---|
| `GET /api/v1/admin/plugins` | admin | Lists registered plugins, events, UI extensions, config, and enabled state. |
| `PUT /api/v1/admin/plugins/{plugin_id}` | admin | Enables/disables a known plugin and stores plugin config. |
| `GET /api/v1/site/extensions` | public | Returns UI extensions for enabled plugins only. |

Runtime service contracts:

```python
await PluginService(session).emit_event("topic.created", payload)
await PluginService(session).public_ui_extensions()
```

Config storage:

- `site_settings.key = "plugins_config"`
- `value = { "<plugin_id>": { "enabled": bool, "config": object } }`

### 3. Contracts

- Plugin definitions are registered in the in-process registry with stable `id`, `name`,
  `version`, supported `events`, `ui_extensions`, and optional async handlers.
- Admin APIs must call the same admin permission gate as other `/admin/*` endpoints and return
  `admin_required` / 403 for non-admin users.
- Unknown plugin IDs return `plugin_not_found` / 404.
- Enable/disable writes update `plugins_config` and write an `audit_logs` row with
  `plugin_config_updated`.
- Public UI extension responses expose only presentation-safe metadata:
  `plugin_id`, `slot`, `key`, `title`, `description`, `component`, and `props`.
- Core services may emit events after their own domain state is flushed but before the final
  commit, so plugin audit rows participate in the same transaction.
- Plugin handlers are an isolation boundary: catch all plugin exceptions, write
  `plugin_hook_failed`, append a failed event result, and let the core request continue.

### 4. Validation & Error Matrix

| Case | Error/Behavior |
|---|---|
| Ordinary user reads `/admin/plugins` | `admin_required` / 403 |
| Admin updates an unknown plugin | `plugin_not_found` / 404 |
| Plugin is disabled | Its UI extensions are absent and event handler is skipped |
| Enabled plugin handles `topic.created` | Handler runs and plugin audit side effects commit with topic |
| Enabled plugin raises | `plugin_hook_failed` audit row is written and topic creation still returns 201 |
| Malformed stored plugin config | Treat plugin as disabled/default rather than crashing public reads |

### 5. Good/Base/Bad Cases

- Good: `ForumService.create_topic()` emits `topic.created`; the example plugin records
  `plugin_example_topic_created`, then search sync and final commit continue normally.
- Base: admin enables `example-topic-tools`; `/site/extensions` returns one `app.nav` extension;
  disabling it removes the extension.
- Bad: a router directly imports plugin definitions and mutates site settings, bypassing
  `PluginService` permission, audit, and config normalization.
- Bad: plugin exceptions propagate out of `emit_event()` and turn a successful topic creation into
  a 500 response.

### 6. Tests Required

- Focused smoke/regression target during roadmap work: `pytest tests/test_plugins.py -q`.
- Assertions:
  - non-admin admin access returns 403;
  - example plugin is listed disabled by default;
  - enabled plugin exposes `app.nav` extension;
  - disabling plugin removes public extension;
  - `topic.created` handler writes an audit log;
  - broken plugin writes `plugin_hook_failed` and core topic creation still succeeds.
- Run `ruff check` on touched plugin/router/service files.

### 7. Wrong vs Correct

#### Wrong

```python
for handler in plugin.handlers:
    await handler(session, payload)  # plugin exception aborts core request
```

#### Correct

```python
await PluginService(session).emit_event("topic.created", payload)
```

`PluginService.emit_event()` owns enable checks, isolation, and failure audit logging.
