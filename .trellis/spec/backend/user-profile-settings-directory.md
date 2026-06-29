# User Profile Settings, Directory, and Activity Backend Contract

## Scenario: Editable profile, privacy-aware public fields, directory, and activity feed

### 1. Scope / Trigger

- Trigger: changing editable profile fields, privacy controls, public user directory, or user activity endpoints.
- Applies to `models/user.py`, `schemas/users.py`, `services/users.py`, `api/v1/users.py`, migrations, and tests.

### 2. Signatures

API routes:

| Method | Path | Auth | Purpose |
|---|---|---:|---|
| `PATCH` | `/api/v1/users/me/profile` | user | Update own profile, privacy, and UI preference fields |
| `GET` | `/api/v1/users/directory?sort=active|level|contribution&limit=` | public | Public member directory without email |
| `GET` | `/api/v1/users/id/{user_id}` | public/optional user | Privacy-filtered profile response by stable user ID |
| `GET` | `/api/v1/users/{username}` | public/optional user | Privacy-filtered profile response |
| `GET` | `/api/v1/users/{username}/activity?type=posts|likes|bookmarks` | privacy-aware | Public activity feed if enabled/visible |

User columns:

- `display_name`, `bio`, `website_url`, `location`
- `profile_visibility: public|members|private`
- `show_activity: bool`
- `interface_theme: system|light|colorful`
- `locale: zh-CN|en-US`

### 3. Contracts

- Public profile and directory responses must never include `email`.
- Browser-facing member pages use `/members/{user_id}` and should fetch profiles via
  `/api/v1/users/id/{user_id}`; username-based endpoints remain available for existing content,
  activity, and relationship APIs.
- `profile_visibility=public` exposes editable profile fields to everyone.
- `profile_visibility=members` exposes editable fields only to logged-in users, self, or admins.
- `profile_visibility=private` exposes editable fields only to self/admins.
- `show_activity=false` hides `/activity` from everyone except self/admins and returns
  `profile_activity_private` / 403 for other callers.
- Directory excludes `profile_visibility=private` users and sorts by active, level, or public contribution counts.
- Activity feed includes only public topics/posts: no private messages, hidden/deleted topics, deleted posts, or private boards.
- Profile URL must be `http(s)`; unsafe schemes return `invalid_profile_url` / 422.

### 4. Validation & Error Matrix

| Case | Expected behavior |
|---|---|
| Anonymous reads public profile | No email; public profile fields visible only if visibility allows |
| Other user reads private profile | Sensitive fields are `null`; counts remain public-safe |
| Other user reads hidden activity | `profile_activity_private` / 403 |
| Owner reads own private profile | Fields visible and `can_edit=true` |
| Invalid website URL | `invalid_profile_url` / 422 |
| Directory response | No `email`; excludes private profiles |

### 5. Good/Base/Bad Cases

- Good: centralize privacy filtering in `UserProfileService` rather than duplicating in routers.
- Base: user edits bio/link, switches visibility private, directory no longer lists that profile.
- Bad: returning `UserPublic` from directory because it includes email.
- Bad: activity feed using interactions without rechecking public topic/board visibility.

### 6. Tests Required

Default roadmap scope is downgraded unless detailed testing is requested:

- `ruff check app/models/user.py app/schemas/users.py app/api/v1/users.py app/services/users.py alembic/versions/0027_user_profile_settings_directory.py tests/test_user_profile_settings_directory.py`
- `pytest tests/test_user_profile_settings_directory.py -q`
- Assertions: profile update round-trip, invalid URL, directory no email, private profile redaction, hidden activity 403.

### 7. Wrong vs Correct

#### Wrong

```python
return UserPublic.model_validate(user)  # leaks email in public directory
```

#### Correct

```python
return UserDirectoryResponse(username=user.username, display_name=user.display_name, ...)
```
