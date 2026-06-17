# Site Theme, Branding, and Text Overrides Backend Contract

## Scenario: Public/admin configurable branding, theme colors, i18n text, and email templates

### 1. Scope / Trigger

- Trigger: changing public branding settings, default logo/favicon values, theme color validation, text override storage, or email template setting keys.
- Applies to `app/services/admin.py`, `app/schemas/admin.py`, `app/api/v1/admin.py`,
  `app/api/v1/site.py`, and consumers of `SiteSettingService`.

### 2. Signatures

Settings keys in `DEFAULT_SITE_SETTINGS`:

| Key | Type | Public | Category | Purpose |
|---|---|---:|---|---|
| `site_title` | string | yes | brand | Display name and document title |
| `site_tagline` | string | yes | brand | Topbar subtitle |
| `brand_primary_color` | string `#RRGGBB` | yes | brand | Primary CSS theme color |
| `brand_accent_color` | string `#RRGGBB` | yes | brand | Accent CSS theme color |
| `brand_logo_url` | string URL | yes | brand | Logo image URL |
| `brand_favicon_url` | string URL | yes | brand | Browser favicon URL |
| `site_text_overrides` | JSON object | yes | text | i18n key -> text overrides |
| `email_notification_subject/body` | string | no | email | Notification email templates |
| `email_digest_subject/body` | string | no | email | Digest email templates |

Validation helpers:

- `SiteSettingService._coerce_string_setting(setting, value)`
- `SiteSettingService._coerce_json_setting(setting, value)`

### 3. Contracts

- `/api/v1/site/settings` returns only `public=true` rows. Email template settings stay admin-only.
- Brand color values must be strict 6-digit hex colors (`#409EFF`); unsafe strings such as `red;`
  return `invalid_site_setting_value`.
- Logo/favicon values must be safe asset URLs: site-relative `/...` or `http(s)://...`, with no
  whitespace.
- `DEFAULT_SITE_SETTINGS["brand_logo_url"].value` is protected and must stay `/logo-lines-mark.png`
  unless there is an explicit logo-change product/design task. Do not change it as part of unrelated
  admin settings, theme, performance, seed-data, or refactor work.
- `DEFAULT_SITE_SETTINGS["brand_favicon_url"].value` is protected and must stay `/favicon.svg`
  unless the same explicit logo/favicon-change task updates frontend assets, frontend branding spec,
  backend branding spec, and focused verification together.
- `site_text_overrides` must be a JSON object with at most 100 keys. Keys match
  `^[a-z0-9_.-]{1,80}$`; values are non-empty strings up to 500 characters after trimming.
- Email template body settings may be up to 4000 characters; other string settings are capped at 512.
- Admin writes still require admin role and write `site_setting_updated` audit logs.
- Public site settings and public plugin UI extensions may use short-lived
  public response caches. Admin update flows must still invalidate frontend
  query caches; backend TTLs must stay short enough that branding/text changes
  settle without manual intervention.

### 4. Validation & Error Matrix

| Case | Expected behavior |
|---|---|
| Ordinary user updates theme | `admin_required` / 403 |
| `brand_primary_color="red;"` | `invalid_site_setting_value` / 422 |
| `brand_logo_url="javascript:..."` | `invalid_site_setting_value` / 422 |
| Unrelated backend setting change edits default `brand_logo_url` | Reject or split into explicit logo-change task |
| Explicit logo-change task edits default `brand_logo_url` | Also update frontend assets/specs and verification |
| `site_text_overrides` is array | `invalid_site_setting_value` / 422 |
| Valid `site_text_overrides` object | Trimmed object persists and appears in public settings |
| Email body template > 512 but <= 4000 chars | Accepted |
| Public settings read | Includes brand/text public keys; excludes email templates |

### 5. Good/Base/Bad Cases

- Good: add new public UI text via `site_text_overrides` rather than a new column or hardcoded route.
- Good: preserve `brand_logo_url="/logo-lines-mark.png"` while changing admin setting labels or caches.
- Base: admin changes `brand_logo_url`; public settings refresh and app shell displays the new logo.
- Bad: changing `DEFAULT_SITE_SETTINGS["brand_logo_url"]` to `/logo.png` during unrelated branding cleanup.
- Bad: exposing `email_notification_body` through `/site/settings`.
- Bad: accepting arbitrary CSS strings as color settings.

### 6. Tests Required

Default roadmap scope is downgraded unless detailed testing is requested:

- `ruff check app/services/admin.py tests/test_admin.py`
- `pytest tests/test_admin.py -q`
- Assert public settings include brand/text keys and invalid color values fail with typed error.
- For explicit default logo/favicon changes: assert backend defaults, frontend `DEFAULT_BRAND_LOGO_URL`,
  public assets, and app shell fallback behavior are updated together.

### 7. Wrong vs Correct

#### Wrong

```python
DEFAULT_SITE_SETTINGS["brand_primary_color"] = DefaultSiteSetting(..., value="red;", public=True)
```

#### Correct

```python
if setting.key in BRAND_COLOR_SETTING_KEYS and HEX_COLOR_PATTERN.fullmatch(trimmed) is None:
    raise ValidationError("invalid_site_setting_value", "Expected a hex color such as #409EFF")
```
