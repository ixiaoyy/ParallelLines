# Site Theme, Branding, and i18n Text Frontend Contract

## Scenario: Applying public branding settings and admin preview/rollback

### 1. Scope / Trigger

- Trigger: changing app shell branding, public setting text fallbacks, theme variable injection, or admin settings preview.
- Applies to `AppShell.vue`, `features/admin/model.ts`, `features/admin/components/AdminSettingsPanel.vue`,
  and `shared/theme/siteBranding.ts`.

### 2. Signatures

Helpers:

| Helper | Purpose |
|---|---|
| `publicSettingString(response, key, fallback)` | Read public string setting with fallback |
| `publicSettingRecord(response, key)` | Read object-valued public setting as string map |
| `siteText(response, key, fallback)` | Resolve `site_text_overrides` with fallback |
| `applySiteBranding(settings, preview?)` | Apply brand colors, favicon, and document title to the current browser |

Admin UI:

- `AdminSettingsPanel` supports `string`, `integer`, `boolean`, and `json` settings.
- Public `brand`/`text` settings can be previewed locally before save and rolled back to server values.

### 3. Contracts

- App shell text that is part of top-level navigation/search/publish auth controls must resolve through
  `siteText(..., key, fallback)` so missing keys safely fall back to Simplified Chinese defaults.
- Logo uses public `brand_logo_url` with `/logo-lines.png` fallback.
- `applySiteBranding()` must validate hex colors before writing CSS variables and must update favicon
  only to safe site-relative or `http(s)` URLs.
- Theme preview is browser-local. It must not call mutation APIs until the admin clicks `保存`.
- Rollback preview reapplies `usePublicSiteSettings().data.settings` and clears preview state.
- JSON settings are edited as formatted JSON text; invalid JSON shows visible status and does not submit.

### 4. Validation & Error Matrix

| Case | Expected UI behavior |
|---|---|
| Missing i18n key | Fallback zh-CN text is displayed |
| Public settings query fails | App shell keeps default title/logo/colors |
| Admin edits color and clicks preview | CSS variables update in current browser only |
| Admin clicks rollback | CSS variables/favicon/title return to server values |
| Invalid JSON override | Status explains invalid JSON; no save mutation runs |
| Save public setting succeeds | Admin/public settings queries invalidate and app shell refreshes |

### 5. Good/Base/Bad Cases

- Good: `siteText(siteSettingsQuery.data.value, "nav.home", "首页")` in app shell labels.
- Good: keep CSS variable and favicon mutation in `shared/theme/siteBranding.ts`.
- Base: admin previews `brand_primary_color`, rolls back, then saves `site_title`.
- Bad: hardcoding new global navigation labels directly in templates.
- Bad: injecting arbitrary CSS from site settings.

### 6. Tests Required

Default roadmap scope is downgraded unless detailed testing is requested:

- `npm run typecheck` in `apps/web`
- `npm run lint` in `apps/web`
- Focused manual/browser smoke when practical: open `/admin`, preview a color/text override, rollback,
  then save one public setting and refresh.

### 7. Wrong vs Correct

#### Wrong

```vue
<RouterLink>首页</RouterLink>
```

#### Correct

```vue
<RouterLink>{{ siteText(siteSettingsQuery.data.value, "nav.home", "首页") }}</RouterLink>
```
