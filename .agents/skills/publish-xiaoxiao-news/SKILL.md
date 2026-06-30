---
name: publish-xiaoxiao-news
description: "Publish a verified news/sports post to ParallelLines using prepared persona channels: 小小资讯 -> 热点资讯, or 小小鸡仔 -> 体坛快讯. Use when the user asks to use 小小资讯, 小小鸡仔, xiaoxiao, 热点资讯, or 体坛快讯 to post/publish sourced news."
---

# Publish Xiaoxiao News

Use this project-local workflow to publish one sourced post to `https://www.pingxingxian.space` through a prepared persona channel:

- `小小资讯` -> `frontier` / `热点资讯`
- `小小鸡仔` -> `sports` / `体坛快讯`

## Workflow

1. Verify the news first:
   - Browse for current primary or reputable sources.
   - Write a concise Chinese post body with source links.
   - Do not publish unverified claims or omit source attribution.
2. Prepare:
   - `title`: 4-180 chars.
   - `body`: Markdown, under 20,000 chars.
   - `tags`: comma-separated. For news, usually `动态,大模型,前沿资讯` plus specifics. For sports, usually `乒乓球,体坛快讯` plus specifics.
   - `slug`: short ASCII slug, for example `ai-model-release-news`.
3. Choose the channel script.
4. Preview with the helper script. Preview is required before publishing:
   - If production rejects the legacy unsigned-session admin token, provide a session-backed admin token:
     - `--admin-token-file .tmp/xiaoxiao-admin-token.txt`, or
     - `PARALLELLINES_ADMIN_ACCOUNT` / `PARALLELLINES_ADMIN_PASSWORD` for a normal admin login.
   - Do not print admin tokens or passwords in chat or logs.

   `小小资讯` -> `热点资讯`:
   ```powershell
   python .agents/skills/publish-xiaoxiao-news/scripts/publish_xiaoxiao_news.py `
     --title "<title>" `
     --slug "<ascii-slug>" `
     --tags "动态,大模型,前沿资讯,openai" `
     --body-file path/to/body.md
   ```

   `小小鸡仔` -> `体坛快讯`:
   ```powershell
   python .agents/skills/publish-xiaoxiao-news/scripts/publish_xiaoxiao_sports.py `
     --title "<title>" `
     --slug "<ascii-slug>" `
     --tags "乒乓球,体坛快讯,WTT" `
     --body-file path/to/body.md
   ```
5. Publish only after preview returns `errors=0` and the topic row says `created`:

   `小小资讯` -> `热点资讯`:
   ```powershell
   python .agents/skills/publish-xiaoxiao-news/scripts/publish_xiaoxiao_news.py `
     --title "<title>" `
     --slug "<ascii-slug>" `
     --tags "动态,大模型,前沿资讯,openai" `
     --body-file path/to/body.md `
     --run
   ```

   `小小鸡仔` -> `体坛快讯`:
   ```powershell
   python .agents/skills/publish-xiaoxiao-news/scripts/publish_xiaoxiao_sports.py `
     --title "<title>" `
     --slug "<ascii-slug>" `
     --tags "乒乓球,体坛快讯,WTT" `
     --body-file path/to/body.md `
     --run
   ```
6. Verify after publish:
   - Confirm the script prints a public topic match.
   - If needed, check `/api/v1/boards/<board-slug>/topics?sort=latest&limit=5`.
   - Report the public URL to the user.

## Notes

- The normal public create-topic API has returned 500 for `小小资讯` because that account currently has a `.local` email that breaks some `UserPublic.email` serialization paths.
- The helper script uses the admin migration import API, which was preview-tested for this workflow. It creates the topic, first post, tags, counts, and search index.
- `publish_xiaoxiao_news.py` defaults the `小小资讯` avatar to `apps/web/public/avatars/xiaoxiao-zixun.png`. On `--run`, it skips upload when the profile already has an avatar unless `--force-author-avatar` is passed.
- `publish_xiaoxiao_sports.py` wraps the shared publisher with defaults for `小小鸡仔`, `sports`, and `apps/web/public/avatars/xiaoxiao-jizai.png`. On `--run`, it uploads the avatar after a successful publish.
- Avatar upload for legacy accounts may return HTTP 500 after the database write if the response serializer hits old profile data. The helper re-checks the public profile and treats a changed `avatar_url` as success.
- The shared publisher sends a browser-like `User-Agent` because production Cloudflare blocks Python's default urllib signature.
- The script can load `apps/api/.env` to sign a short-lived legacy admin JWT, but production may require a session-backed admin token with `sid`. Prefer `--admin-token-file` or admin login environment variables when publishing to production. Never print or disclose `JWT_SECRET_KEY`, generated tokens, or publisher passwords.
- Do not publish to legacy, SSH-only, or non-public environments; verify against `https://www.pingxingxian.space`.
