# Frontend Component Guidelines

## Style

- Use Vue 3 Single File Components with `<script setup lang="ts">`.
- Use Composition API only.
- Keep props explicit and typed with interfaces.
- Use emits for user actions; parent components coordinate mutations.
- Prefer slots for layout composition.
- Use Ant Design Vue as the default UI framework. Project components in `shared/ui` should wrap Ant Design Vue primitives when customization is needed.

## Style Organization

- Use SCSS (`.scss`, not indented `.sass`) as the project stylesheet syntax.
- Global reset/token files live in `shared/styles/*.scss` and are imported from `src/main.ts`.
- Route pages and non-trivial feature components must keep style in a co-located file:

```vue
<style scoped lang="scss" src="./HomePage.scss"></style>
```

- Keep only tiny primitive styles inline in `shared/ui` when the style block is short and tightly coupled to the wrapper.
- Use SCSS nesting sparingly; keep selectors shallow enough to preserve Vue scoped-style readability.

## Component Size and Decomposition Contract

**What**: Route pages compose data state, routing, and feature components; they must not become a dumping ground for every panel, toolbar, sidebar, and card in the page.

**Why**: Large page files made the topic-detail layout hard to reason about and allowed wrapper-specific CSS bugs to hide across hundreds of lines. Splitting the page into feature components keeps UI changes reviewable and prevents future visual regressions.

**Limits**:

- Treat `250` lines as the warning threshold for route-level `.vue` files and `300` lines as the warning threshold for page-level `.scss` files.
- Before adding non-trivial markup to a file already near the threshold, extract a named component under the owning feature module (`features/topics/components/*`, `features/posts/components/*`, etc.).
- A route page may keep orchestration functions such as query composition, draft handling, and event wiring, but presentational sections such as hero, toolbar, sidebars, stat panels, and repeated cards belong in feature components.
- Co-locate each extracted component's SCSS file beside its `.vue`; do not move the bloat from one page stylesheet into another single global stylesheet.
- When styling wrapped Ant Design Vue components such as `UiCard`, target the wrapper body explicitly (for example, `.my-card :deep(.ant-card-body)`) and set grid placement on direct children when layout order matters.

### Wrong

```vue
<!-- pages/topic/TopicDetailPage.vue -->
<template>
  <!-- Hundreds of lines of hero, toolbar, sidebar, post stream, and reply form markup here -->
</template>
```

### Correct

```vue
<!-- pages/topic/TopicDetailPage.vue -->
<template>
  <TopicDetailHero :topic="topic" :stats="topicStats" />
  <TopicThreadToolbar @copy-link="copyTopicLink" />
  <TopicDetailSidebar :topic="topic" :posts="displayedPosts" />
</template>
```

## Design Tokens

Use CSS variables from `shared/styles/tokens.scss`:

```scss
--bg-app: #F8FAFC;
--primary: #409EFF;
--accent-geek: #10B981;
--title: #334155;
--text: #475569;
--code-bg: #1E1E1E;
```

## Forum UI Patterns

- `TopicCard` must show title, board, tags, author, reply count, view count, and last activity.
- `PostItem` must show floor number, author, timestamp, rendered content, and action bar.
- `ComposerDrawer` must support title/category/tags for new topics and compact reply mode for posts.
- `MarkdownRenderer` should receive sanitized/cooked HTML from the API, not render unsafe raw HTML in the client.


## Homepage Visual and Layout Contract

**What**: The home/discovery page follows the checked-in reference `parallel-lines-forum-design.html` for palette and surface treatment: blue/cyan gradients, light blue-white page atmosphere, translucent white panels, rounded pill topbar, and calm forum density. Do not introduce purple background layers for this page.

**Layout**: Desktop home uses a Discourse/Horizon-style variable-width grid:

```scss
.home-grid {
  grid-template-columns: minmax(13.5rem, 17em) minmax(0, 1fr);
}
```

- Left rail: board shortcuts and tags; sticky on desktop.
- Main column: hero, optional community guide posts, and topic feed.
- Do not duplicate board/tag discovery cards in the main column or add a right rail on the home page.
- Avoid explanatory intro blocks around the home topic feed; keep only actions, filters, and real content.
- Home topic feed tabs must use plain community labels (`最新`, `热门`, `精华`) and avoid internal product jargon.
- Avatar level styles must be outer rings only; never recolor the avatar body by board or level.
- At small widths the page becomes one column and the left rail is hidden.

**Contracts**:
- `HomePage.vue` owns semantic layout and real API-backed state; it must not render fixture topics/boards/tags in production paths.
- `HomePage.scss` owns page-specific responsive composition and must use tokens from `shared/styles/tokens.scss` for fixed colors.
- `AppShell.scss` owns the pill topbar and global blue/cyan background atmosphere.

**Tests Required**: After changing this layout, run `pnpm --dir apps/web lint`, `pnpm --dir apps/web typecheck`, `pnpm --dir apps/web build`, then perform a browser visual check on `/` for desktop and narrow widths.
## Accessibility

- Interactive elements must be buttons or links, not clickable divs.
- Preserve visible focus states.
- Notification counts must have accessible labels.
- Code blocks should include a copy button with an accessible name.

## Anti-patterns

- No inline hex colors outside token definitions.
- No large page-level `<style>` blocks inside `.vue`; extract to co-located `.scss`.
- No new plain `.css` files unless they are third-party vendor imports that cannot be converted.
- No component making hidden API mutations on mount.
- Do not rebuild complex Ant Design Vue primitives from scratch unless product needs require it.

