# Component Guidelines

## Standard Shape

Use Vue 3 single-file components with `<script setup lang="ts">`, followed by the
template and a scoped style block. Larger components load a colocated SCSS file:

```vue
<script setup lang="ts">
// imports, typed props/events, reactive state, and handlers
</script>

<template>
  <!-- semantic markup -->
</template>

<style scoped lang="scss" src="./ComponentName.scss"></style>
```

`features/topics/components/TopicCard.vue` and
`features/admin/components/AdminConsoleShell.vue` are representative. Small
domain-neutral controls such as `shared/ui/Button.vue` may keep concise scoped
styles inline.

## Props, Events, and Ownership

- Declare props with `defineProps<T>()`. Use `withDefaults` for optional values;
  `TopicCard.vue` is the reference.
- Declare emitted events with typed tuple payloads using `defineEmits`.
- Keep destructive flows, modal ownership, and server mutations in the parent
  that has the full workflow context. A child may emit intent, as
  `TopicCard.vue` does with `deleteTopic`.
- Use `computed` for derived display state and `ref` for mutable UI state. Do not
  copy query results into a second mutable object unless an editable draft is
  required.
- Route pages should remain thin. Reusable feature panels own their loading,
  empty, error, and populated presentation when they own the corresponding
  query, as `AdminWorkbenchPanel.vue` does.
- Use `defineAsyncComponent` for optional heavy UI that is only needed on a
  specific shell or route. `AdminConsoleShell.vue` lazily loads the notification
  center.

## Interaction and Accessibility

- Use native `button`, `a`/`RouterLink`, headings, lists, and landmarks before
  adding ARIA.
- Icon-only buttons need an accessible name. Decorative Ant Design icons use
  `aria-hidden="true"`.
- Loading and failure states use appropriate live semantics (`role="status"` or
  `role="alert"`) and visible recovery actions.
- Preserve visible `:focus-visible` styles. Drawer and modal-like interactions
  must manage focus and remove hidden content from interaction; the admin shell's
  `inert`, focus restoration, and Tab trap are the local reference.
- Touch-critical actions must provide at least a 44 by 44 CSS-pixel target.
- Never require hover to discover or execute an action. Any motion needs a
  `prefers-reduced-motion` fallback.

## UI Reuse

- Search `shared/ui/` before introducing buttons, avatars, badges, skeletons,
  cards, tabs, password fields, or empty states.
- Use `UiButton` tones instead of restyling Ant Design primary buttons locally.
- Keep Ant Design icons within the existing visual vocabulary rather than adding
  a second icon set.
- Use runtime site text and branding helpers on configurable admin surfaces;
  `AdminConsoleShell.vue` uses `siteText` and `publicSettingString`.

## Comments

Comment non-obvious contracts, side effects, focus behavior, compatibility
fallbacks, or public helper behavior. Do not narrate obvious template markup or
simple computed values. Existing focused examples are in `useMediaQuery.ts` and
`AdminConsoleShell.vue`.

## Avoid

- Untyped props or emits.
- Click handlers on non-interactive elements.
- A page component that duplicates a feature component's business logic.
- Raw API calls or cache mutation inside presentational children.
- Hiding loading, empty, error, unauthorized, or reduced-motion states while
  styling only the successful desktop state.
