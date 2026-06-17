# Site Theme, Branding, and i18n Text Frontend Contract

## Scenario: Applying public branding settings and admin preview/rollback

### 1. Scope / Trigger

- Trigger: changing app shell branding, logo/favicons, public setting text fallbacks, theme variable injection, or admin settings preview.
- Applies to `AppShell.vue`, `features/admin/model.ts`, `features/admin/components/AdminSettingsPanel.vue`,
  `shared/theme/siteBranding.ts`, and protected files under `apps/web/public/*logo*` or `apps/web/public/favicon.*`.

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

Protected brand assets:

| Asset / constant | Canonical value | Contract |
|---|---|---|
| Topbar default logo | `/logo-lines-mark.png` | Used by `DEFAULT_BRAND_LOGO_URL`; protected from incidental changes |
| Legacy topbar values | `/logo-lines.png`, `/favicon.svg` | Must fall back to `/logo-lines-mark.png`, not be revived as defaults |
| Browser favicon | `/favicon.svg` | Used by `brand_favicon_url`; not a substitute for the topbar logo |

### 3. Contracts

- App shell text that is part of top-level navigation/search/publish auth controls must resolve through
  `siteText(..., key, fallback)` so missing keys safely fall back to Simplified Chinese defaults.
- Topbar logo uses public `brand_logo_url` with `/logo-lines-mark.png` fallback; the old `/logo-lines.png`
  default is a large PNG and should not be loaded on the critical home-page path. Favicon uses
  `brand_favicon_url` with `/favicon.svg` fallback.
- The built-in/default logo is a protected brand asset. Do not replace, redraw, rename, delete, or repoint
  `apps/web/public/logo-lines-mark.png`, `DEFAULT_BRAND_LOGO_URL`, or `LEGACY_BRAND_LOGO_URLS`
  during ordinary performance, layout, theme, or component refactors.
- A real logo change must be an explicit product/design request and must update this spec, backend branding
  defaults, app shell rendering, public assets, and focused verification in the same change set.
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
| Public `brand_logo_url` is `/logo-lines.png` or `/favicon.svg` | App shell displays `/logo-lines-mark.png` |
| Unrelated UI/theme/performance change edits logo asset or default path | Reject or split into an explicit logo-change task |
| Admin edits color and clicks preview | CSS variables update in current browser only |
| Admin clicks rollback | CSS variables/favicon/title return to server values |
| Invalid JSON override | Status explains invalid JSON; no save mutation runs |
| Save public setting succeeds | Admin/public settings queries invalidate and app shell refreshes |

### 5. Good/Base/Bad Cases

- Good: `siteText(siteSettingsQuery.data.value, "nav.home", "首页")` in app shell labels.
- Good: keep CSS variable and favicon mutation in `shared/theme/siteBranding.ts`.
- Good: preserve `DEFAULT_BRAND_LOGO_URL = "/logo-lines-mark.png"` while optimizing app shell render code.
- Base: admin previews `brand_primary_color`, rolls back, then saves `site_title`.
- Bad: replacing `/logo-lines-mark.png` while doing an unrelated homepage or bundle-size cleanup.
- Bad: using `/favicon.svg` as the topbar logo because it is already available.
- Bad: hardcoding new global navigation labels directly in templates.
- Bad: injecting arbitrary CSS from site settings.

### 6. Tests Required

Default roadmap scope is downgraded unless detailed testing is requested:

- `npm run typecheck` in `apps/web`
- `npm run lint` in `apps/web`
- For app shell/logo changes: assert `DEFAULT_BRAND_LOGO_URL` remains `/logo-lines-mark.png`, legacy values
  still map to it, and favicon changes do not alter the topbar logo.
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
