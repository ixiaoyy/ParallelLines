---
name: publish-xiaoxiao-news
description: "Publish a verified news post to ParallelLines 热点资讯 using the 小小资讯 account. Use when the user asks to use 小小资讯, 小小资讯账号, or xiaoxiao to post/publish a news article, especially after asking Codex to search, summarize, and publish AI/tech news."
---

# Publish Xiaoxiao News

Use this project-local workflow to publish one news post as `小小资讯` to the public `frontier` board (`热点资讯`) on `https://www.pingxingxian.space`.

## Workflow

1. Verify the news first:
   - Browse for current primary or reputable sources.
   - Write a concise Chinese post body with source links.
   - Do not publish unverified claims or omit source attribution.
2. Prepare:
   - `title`: 4-180 chars.
   - `body`: Markdown, under 20,000 chars.
   - `tags`: usually `动态,大模型,前沿资讯` plus specific tags.
   - `slug`: short ASCII slug, for example `ai-model-release-news`.
3. Preview with the helper script. Preview is required before publishing:
   ```powershell
   python .agents/skills/publish-xiaoxiao-news/scripts/publish_xiaoxiao_news.py `
     --title "<title>" `
     --slug "<ascii-slug>" `
     --tags "动态,大模型,前沿资讯,openai" `
     --body-file path/to/body.md
   ```
4. Publish only after preview returns `errors=0` and the topic row says `created`:
   ```powershell
   python .agents/skills/publish-xiaoxiao-news/scripts/publish_xiaoxiao_news.py `
     --title "<title>" `
     --slug "<ascii-slug>" `
     --tags "动态,大模型,前沿资讯,openai" `
     --body-file path/to/body.md `
     --run
   ```
5. Verify after publish:
   - Confirm the script prints a public topic match.
   - If needed, check `/api/v1/boards/frontier/topics?sort=latest&limit=5`.
   - Report the public URL to the user.

## Notes

- The normal public create-topic API has returned 500 for `小小资讯` because that account currently has a `.local` email that breaks some `UserPublic.email` serialization paths.
- The helper script uses the admin migration import API, which was preview-tested for this workflow. It creates the topic, first post, tags, counts, and search index.
- The script loads `apps/api/.env` only to sign a short-lived admin JWT. Never print or disclose `JWT_SECRET_KEY`, generated tokens, or publisher passwords.
- Do not publish to legacy, SSH-only, or non-public environments; verify against `https://www.pingxingxian.space`.
