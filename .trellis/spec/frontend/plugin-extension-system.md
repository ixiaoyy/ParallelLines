# Plugin Extension System UI Contract

## Scenario: Admin plugin management and safe frontend extension slots

### 1. Scope / Trigger

- Trigger: rendering plugin-provided UI entries, adding extension slots, or changing admin plugin
  configuration UI.
- Applies to `features/plugins/`, `AppShell.vue`, `AdminDashboardPage.vue`,
  `shared/api/queryKeys.ts`, and generated OpenAPI DTO usage.

### 2. Signatures

Frontend API functions:

| Function | Backend endpoint | Return |
|---|---|---|
| `fetchSiteExtensions()` | `GET /api/v1/site/extensions` | `PluginUiExtensionResponse[]` |
| `fetchAdminPlugins()` | `GET /api/v1/admin/plugins` | `PluginResponse[]` |
| `updateAdminPlugin(pluginId, payload)` | `PUT /api/v1/admin/plugins/{plugin_id}` | `PluginResponse` |

Query keys:

- `queryKeys.siteExtensions`
- `queryKeys.adminPlugins`

Primary components:

- `PluginSlot.vue` renders enabled extensions for a named slot.
- `AdminPluginsPanel.vue` lists registered plugins and toggles enabled state.

### 3. Contracts

- API DTO types must come from `shared/api/generated.ts`; UI-only helpers may live in
  `features/plugins/model.ts`.
- The first supported slot is `app.nav`; app shell renders it in desktop topbar and mobile nav.
- Plugin extension props are untrusted metadata. `PluginSlot` may render safe internal links only:
  `props.href` must be a string starting with `/`; otherwise render non-clickable text.
- Components never dynamically import arbitrary plugin component names. `component` is metadata for
  an allowlist-style renderer; unsupported components fall back to safe link/text behavior.
- Admin plugin toggles invalidate `adminPlugins`, `siteExtensions`, and `adminRoot` queries so the
  public slot disappears immediately after disable.
- Public extension query must not require authentication.

### 4. Validation & Error Matrix

| Case | Expected behavior |
|---|---|
| No plugins enabled | `PluginSlot` renders nothing |
| Enabled `app.nav` extension with safe `/path` href | Renders a `RouterLink` with plugin label |
| Extension has missing/unsafe `href` | Renders inert text, not an external link |
| Admin plugin query fails | Admin panel shows a visible plugin config error |
| Toggle is pending | Toggle buttons are disabled to avoid duplicate writes |
| Plugin disabled | Site extensions query invalidates and entry disappears |

### 5. Good/Base/Bad Cases

- Good: app shell imports `PluginSlot` and passes `slot-name="app.nav"`; the slot owns query/filter
  behavior and renders no markup when empty.
- Base: admin opens `/admin`, toggles the example plugin, and the topbar/mobile plugin entry appears
  after query invalidation.
- Bad: frontend trusts `props.href="https://..."` or `javascript:...` and renders it directly.
- Bad: `AdminDashboardPage.vue` calls `apiPut` directly instead of using `features/plugins/queries`.

### 6. Tests Required

- Default roadmap scope: `pnpm --dir apps/web typecheck` and `pnpm --dir apps/web lint`.
- OpenAPI contract changes must also pass `pnpm --dir apps/web openapi:check`.
- Full browser/component tests are deferred unless requested or release readiness requires them.

### 7. Wrong vs Correct

#### Wrong

```vue
<a :href="extension.props.href">{{ extension.title }}</a>
```

#### Correct

```vue
<RouterLink v-if="extensionHref(extension)" :to="extensionHref(extension) ?? '/'">
  {{ extensionLabel(extension) }}
</RouterLink>
```

The helper enforces an internal-route-only extension contract.
