---
name: add-persona-account
description: "Add or update a ParallelLines persona/alt account. Use when the user asks to add a 马甲账号, 预设账号, persona user, seeded user, bot-like ordinary user, login test account, or account with generated/static avatar, including Alembic user seeding, persona script updates, password hash validation, and avatar asset placement."
---

# Add Persona Account

Use this workflow to add one durable ordinary persona account to ParallelLines.

## Steps

1. Confirm account intent:
   - Required: username/display name.
   - Default role/status: `role="user"`, `status="active"`.
   - Default password for login-capable 马甲 accounts follows existing smoke-test convention: `oldhuai123`, unless the user requests another password.
   - Choose a response-schema-valid email, preferably `ascii-slug@pingxingxian.space`; avoid new `.local` emails for public API users.
2. Gather evidence first:
   ```powershell
   rg -n "<username>|<email>|persona|马甲|oldhuai123|avatar_url" apps/api apps/web .trellis/spec -g "!**/node_modules/**" -g "!**/dist/**"
   git status --short --branch
   ```
   Verify the username/email/avatar path are unused before editing.
3. Read only relevant specs:
   - `.trellis/spec/backend/user-profile-settings-directory.md`
   - `.trellis/spec/backend/uploads-attachments.md`
   - `.trellis/spec/frontend/user-profile-settings-directory.md`
   - `.trellis/spec/frontend/uploads-attachments.md`
4. Avatar workflow:
   - If the user asks to generate an avatar, use `$imagegen` built-in mode.
   - Inspect the generated result.
   - Copy the selected image into `apps/web/public/avatars/<ascii-slug>.png`; leave the original generated image in place.
   - Store user `avatar_url` as `/avatars/<ascii-slug>.png`; `resolveApiAssetUrl()` will use this as a same-origin static asset.
   - Do not modify protected logo/favicon assets.
5. User seed migration:
   - Add an Alembic data migration after the current mainline/local head.
   - Define constants for username, email, avatar URL, password hash, and bio.
   - Generate password hashes with the API environment:
     ```powershell
     uv run python -c "from app.core.security import hash_password; print(hash_password('<password>'))"
     ```
   - Verify hashes carefully; in PowerShell, use single quotes around commands containing `$argon2id`:
     ```powershell
     uv run python -c 'from app.core.security import verify_password; print(verify_password("<password>", "<hash>"))'
     ```
   - Upsert only when username/email match the same row; raise on conflicts.
   - On downgrade, leave the account in place to avoid deleting authored content.
   - Every new helper function needs a docstring covering purpose, key parameters, return value, and side effects.
6. Persona script update:
   - If this is a general 马甲/persona account, add it to `apps/api/scripts/seed_persona_discussions.py` `PERSONAS`.
   - Do not add article content unless the user asks for seeded posts.
7. Verify:
   ```powershell
   git diff --check -- <changed-files>
   python -m py_compile <new-migration.py> apps/api/scripts/seed_persona_discussions.py
   uv run ruff check alembic/versions/<new-migration.py> scripts/seed_persona_discussions.py
   ```
   Do not run `pnpm test:api` unless the user explicitly says the local test database is ready.
8. Final review:
   - Search username/email/avatar path again.
   - Check `git status --short` and call out unrelated dirty files.
   - Report login username, email, avatar URL, migration path, persona script path, and validations.

## Output

- Username/email and whether the account is login-capable.
- Avatar asset path and `avatar_url`.
- Alembic migration path.
- Persona script update, if any.
- Validation results.
