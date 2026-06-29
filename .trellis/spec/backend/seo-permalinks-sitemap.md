# SEO, Permalinks, and Sitemap Contract

## Scenario: Public indexing, canonical links, and legacy topic redirects

### 1. Scope / Trigger

- Trigger: adding or changing `sitemap.xml`, `robots.txt`, canonical metadata, share metadata,
  public permalink redirects, or crawler-visible filtering.
- Applies to `app/api/seo.py`, `app/services/seo.py`, `app/schemas/seo.py`,
  `app/main.py`, `app/api/v1/router.py`, and public board/topic/user query behavior.

### 2. Signatures

Root web endpoints:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/sitemap.xml` | XML sitemap for public home, board directory, public boards, public topics, and active user profiles. |
| `GET` | `/robots.txt` | Basic crawler policy and sitemap location. |
| `GET` | `/t/{legacy_slug}/{topic_id}` | 301 redirect from old slug-first topic URL to canonical topic URL. |
| `GET` | `/p/{topic_id}` | 301 redirect from compact permalink to canonical topic URL. |

API endpoints:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/seo/meta?path=` | Return canonical URL, title, description, OpenGraph, Twitter Card, and robots fields for a public route. |

Service signatures:

- `SeoService.sitemap_urls(base_url) -> list[SitemapUrl]`
- `SeoService.robots_txt(base_url) -> str`
- `SeoService.meta_for_path(path, base_url) -> SeoMetaResponse`
- `SeoService.legacy_topic_redirect(topic_id, base_url) -> LegacyTopicRedirect`
- `SeoService.build_sitemap_xml(urls) -> str`

Canonical paths:

- Topic: `/topics/{topic_id}/{topic_slug}`
- Board: `/b/{board_slug}`
- User: `/members/{user_id}`

### 3. Contracts

- Sitemap is anonymous/public-only. It must include only:
  - `Board.visibility == "public"`;
  - `Topic.visibility == "public"`;
  - `Topic.status != "hidden"`;
  - `Topic.deleted_at is NULL`;
  - `Topic.merged_into_topic_id is NULL`;
  - active user profiles.
- Private, invite-only, unlisted, hidden, deleted, and private-message topics must not appear in
  sitemap or SEO metadata responses.
- Legacy redirects must not leak private target existence. If the target is not public, return the
  same `topic_not_found` 404 shape as normal topic reads.
- Root SEO endpoints use browser paths, not `/api/v1` paths, because crawlers request
  `/sitemap.xml`, `/robots.txt`, and legacy URLs directly.
- `SeoMetaResponse.canonical_url` and `og_url` are absolute URLs derived from the request base URL.
- Topic metadata uses the first visible post Markdown as the description source, safely stripped and
  truncated. Do not include raw HTML or private post bodies in metadata.

### 4. Validation & Error Matrix

| Case | Expected behavior |
|---|---|
| Public board/topic exists | Sitemap includes canonical board/topic URL. |
| Private board has topic | Sitemap excludes both board and topic IDs/slugs. |
| Hidden/deleted/merged topic | Sitemap excludes it. |
| `/t/old/{public_topic_id}` | 301 to `/topics/{id}/{current_slug}`. |
| `/t/old/{private_topic_id}` | `404 topic_not_found`; no redirect target leaked. |
| `/api/v1/seo/meta?path=/topics/{id}/old` | Returns canonical current slug and `og_type=article`. |
| Unknown path | `404 seo_meta_not_found`. |

### 5. Good/Base/Bad Cases

- Good: crawler requests `/sitemap.xml`; only public board/topic/user URLs appear.
- Good: a shared old topic URL redirects by stable ID to the current canonical slug.
- Base: SPA pages still update browser meta tags after data loads; backend SEO metadata provides a
  crawler/pre-render contract.
- Bad: building sitemap from frontend routes without checking board/topic visibility.
- Bad: using authenticated current-user visibility for sitemap; sitemap must be anonymous public.

### 6. Tests Required

- Downgraded roadmap scope:
  - `ruff check app tests/test_seo_permalinks.py`
  - `pytest tests/test_seo_permalinks.py -q`
- Assertions:
  - public board/topic are present in sitemap;
  - private board/topic are absent;
  - robots references the sitemap;
  - old topic URL redirects to canonical URL;
  - private old topic URL returns 404;
  - metadata endpoint returns canonical URL and article OG type.

### 7. Wrong vs Correct

#### Wrong

```python
topics = await session.scalars(select(Topic))
```

#### Correct

```python
topics = await session.scalars(
    select(Topic).join(Topic.board).where(
        Board.visibility == "public",
        Topic.visibility == "public",
        Topic.status != "hidden",
        Topic.deleted_at.is_(None),
    )
)
```
