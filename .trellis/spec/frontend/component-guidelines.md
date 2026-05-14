# Frontend Component Guidelines

## Style

- Use Vue 3 Single File Components with `<script setup lang="ts">`.
- Use Composition API only.
- Keep props explicit and typed with interfaces.
- Use emits for user actions; parent components coordinate mutations.
- Prefer slots for layout composition.
- Use Ant Design Vue as the default UI framework. Project components in `shared/ui` should wrap Ant Design Vue primitives when customization is needed.

## Design Tokens

Use CSS variables from `shared/styles/tokens.css`:

```css
--bg-app: #F8F9FA;
--primary: #3B82F6;
--accent-geek: #10B981;
--title: #111827;
--text: #4B5563;
--code-bg: #1E1E1E;
```

## Forum UI Patterns

- `TopicCard` must show title, board, tags, author, reply count, view count, and last activity.
- `PostItem` must show floor number, author, timestamp, rendered content, and action bar.
- `ComposerDrawer` must support title/category/tags for new topics and compact reply mode for posts.
- `MarkdownRenderer` should receive sanitized/cooked HTML from the API, not render unsafe raw HTML in the client.

## Accessibility

- Interactive elements must be buttons or links, not clickable divs.
- Preserve visible focus states.
- Notification counts must have accessible labels.
- Code blocks should include a copy button with an accessible name.

## Anti-patterns

- No inline hex colors outside token definitions.
- No component making hidden API mutations on mount.
- Do not rebuild complex Ant Design Vue primitives from scratch unless product needs require it.
