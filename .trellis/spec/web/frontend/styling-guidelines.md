# Styling Guidelines

## Sources of Truth

The frontend uses project-owned CSS custom properties and Ant Design Vue:

- `shared/styles/tokens.scss` defines global color, text, surface, border, and
  spacing-related tokens.
- `shared/styles/button-surfaces.scss` owns primary and soft button surfaces.
- `app/App.vue` configures Ant Design runtime theme values.
- `shared/theme/siteBranding.ts` applies runtime site branding while preserving
  the primary-button contract.
- `shared/theme/boardPalette.ts` owns board and tag tones.

Use these sources instead of introducing local near-duplicate colors.

## Protected Brand and Primary Action Rules

- The official top-bar logo is `/logo-lines-mark.png`; the favicon is
  `/favicon.svg`. Do not replace, redraw, rename, or change their defaults during
  ordinary UI work.
- Primary actions use a solid `#409EFF` surface with white text through
  `UiButton`, Ant Design primary buttons, or `--btn-primary-*`.
- Do not use `--gradient-brand` for buttons. It is decorative only.
- Soft secondary surfaces use `--theme-soft-*`; do not turn them into a solid
  primary button on hover.
- Board identity colors come from `boardPalette.ts`. Do not overwrite board-tone
  selections with the global primary blue.

The repository `AGENTS.md` contains the complete synchronized source list for
brand-color changes and must be read before changing any of these contracts.

## Component Styles

- Use scoped styles. Colocate substantial SCSS in a same-name file and reference
  it from the component.
- Use BEM-like component prefixes that make ownership obvious, such as
  `admin-console-shell__bottom-item` and `topic-row--pinned`.
- Use `:deep(...)` only to style a known child component or Ant Design internal
  class from a scoped stylesheet.
- Prefer CSS Grid for two-dimensional workbench layouts and Flexbox for one-axis
  alignment. Add `min-width: 0` to grid/flex children that must truncate.
- Reuse text-overflow patterns deliberately. Do not hide content that must remain
  understandable on mobile.

## Responsive and Interaction Rules

- Choose breakpoints where the layout stops working. Existing admin navigation
  switches at `860px`; a component may use a narrower content breakpoint inside
  that shell.
- Keep all core functionality available on phone widths. Reflow or progressively
  disclose it instead of removing it.
- Fixed mobile navigation must account for
  `env(safe-area-inset-bottom)` in both the navigation and content clearance.
- Core touch targets are at least 44 by 44 CSS pixels.
- Hover styles may enhance an interaction but cannot be its only affordance.
- Use `:focus-visible` and preserve a visible focus ring.
- Motion should communicate state and normally stay within 150–250ms. Add a
  `prefers-reduced-motion: reduce` rule for every transition or animation group.

## Visual Character

ParallelLines product surfaces are calm, technical, bright, and scan-friendly.
Operational pages prioritize real data density and clear state over decoration.
Avoid glass effects, decorative SaaS metric cards, oversized empty heroes,
unnecessary gradients, deep shadows, excessive rounding, and fabricated charts
or trends.

## Verification

For responsive work, inspect at least 320px, 390px, the owning breakpoint, and a
desktop viewport. Check horizontal overflow, text wrapping, focus, touch targets,
safe-area clearance, and loading/error/empty states.
