# SEO, Permalinks, and Share Metadata UI Contract

## Scenario: Browser canonical metadata for public SPA pages

### 1. Scope / Trigger

- Trigger: changing topic, board, or user profile routes; adding social preview metadata; changing
  canonical URL helpers; or updating share/permalink behavior.
- Applies to `shared/seo/meta.ts`, `pages/topic/TopicDetailPage.vue`,
  `pages/board/BoardPage.vue`, `pages/user/UserProfilePage.vue`,
  `shared/router/topicRoutes.ts`, `app/router.ts`, and `index.html`.

### 2. Signatures

Composable:

- `useSeoMeta(source: MaybeRefOrGetter<SeoMetaInput | null | undefined>)`

Input:

```ts
interface SeoMetaInput {
  title: string;
  description: string;
  canonicalPath: string;
  ogType?: "website" | "article" | string;
}
```

Managed tags:

- `document.title`
- `<link rel="canonical">`
- `meta[name="description"]`
- `meta[name="robots"]`
- `meta[property="og:type"]`
- `meta[property="og:title"]`
- `meta[property="og:description"]`
- `meta[property="og:url"]`
- `meta[name="twitter:card"]`
- `meta[name="twitter:title"]`
- `meta[name="twitter:description"]`

Canonical browser paths:

- Topic: `/topics/{topic.id}/{topic.slug}`
- Board: `/b/{board.slug}`
- User: `/members/{profile.id}`

### 3. Contracts

- Page components set metadata only after public API data loads. Do not invent title/description
  from route params alone if the backend returned an error.
- Topic pages use `ogType: "article"`, title `主题 · 版块 · 平行线`, and description from
  `TopicCardVM.excerpt`.
- Board and user profile pages use `website` metadata with backend-visible names/counts.
- `useSeoMeta` owns DOM tag mutation. Page components must not manually query and mutate meta tags.
- `index.html` keeps safe default metadata for initial load before async page data arrives.
- Canonical links must use browser-facing routes, not `/api/v1` endpoints.

### 4. Validation & Error Matrix

| Case | Expected behavior |
|---|---|
| Topic loads | Title, canonical, OG, and Twitter metadata point to `/topics/{id}/{slug}`. |
| Topic route has stale slug | Existing route replacement updates path; metadata uses loaded current slug. |
| Board loads | Canonical points to `/b/{slug}` and description uses board description. |
| User profile loads | Canonical points to `/members/{user_id}` and description uses public content counts. |
| Page query errors | Existing default/previous metadata remains; no route-param-only private data is exposed. |

### 5. Good/Base/Bad Cases

- Good: `TopicDetailPage.vue` computes SEO metadata from `topicQuery.data`.
- Good: `index.html` includes default Chinese description/OG tags for first paint.
- Base: backend `/api/v1/seo/meta` is available for future pre-render/SSR, while SPA updates tags
  at runtime today.
- Bad: adding direct `document.querySelector("meta")` code to every page.
- Bad: canonical URL includes `/api/v1/topics/{id}` instead of `/topics/{id}/{slug}`.

### 6. Tests Required

- Downgraded roadmap scope:
  - `npm run typecheck`
  - `npm run lint`
- Focused browser/manual smoke when a local server is already running:
  - open public topic/board/user page;
  - inspect `<link rel="canonical">` and OG/Twitter tags;
  - verify stale topic slug redirects to current slug.

### 7. Wrong vs Correct

#### Wrong

```ts
document.title = String(route.params.slug);
```

#### Correct

```ts
useSeoMeta(
  computed(() =>
    topic.value
      ? {
          title: `${topic.value.title} · ${topic.value.boardName} · 平行线`,
          description: topic.value.excerpt,
          canonicalPath: `/topics/${topic.value.id}/${topic.value.slug}`,
          ogType: "article",
        }
      : null,
  ),
);
```
