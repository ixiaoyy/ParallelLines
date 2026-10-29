import type { CSSProperties } from "vue";

import { CATEGORY_VISUAL_ALIASES, type CategoryVisualKey } from "@/features/catalog/categoryVisuals";

interface CatalogCategorySectionTheme {
  readonly surface: string;
  readonly accent: string;
  readonly tail?: CategoryVisualKey;
}

/** Whole-section paper tones for existing category keys. This registry creates no categories. */
export const CATALOG_CATEGORY_SECTION_THEMES = {
  action: { surface: "#eee2d2", accent: "#866247", tail: "action" },
  shooting: { surface: "#dfe7ec", accent: "#587281", tail: "shooting" },
  racing: { surface: "#d9e9e0", accent: "#4c7872", tail: "racing" },
  stages: { surface: "#f0e2dc", accent: "#986d53", tail: "stages" },
  puzzle: { surface: "#dce9df", accent: "#517663", tail: "puzzle" },
  rts: { surface: "#e9e3d2", accent: "#766d50", tail: "rts" },
  "tower-defense": { surface: "#dce4cf", accent: "#71765d", tail: "tower-defense" },
  cards: { surface: "#eee0d9", accent: "#8c6b50", tail: "cards" },
  rpg: { surface: "#e1e2ec", accent: "#6c7184", tail: "rpg" },
  simulation: { surface: "#eee9d5", accent: "#85734d", tail: "simulation" },
  casual: { surface: "#deebef", accent: "#587a80", tail: "casual" },
  romance: { surface: "#efdee6", accent: "#956b80", tail: "romance" },
  horror: { surface: "#e1dfe8", accent: "#786b81", tail: "horror" },
  exploration: { surface: "#d9e8e3", accent: "#54796c", tail: "exploration" },
  farming: { surface: "#e6e9cd", accent: "#748052", tail: "farming" },
} as const satisfies Readonly<Record<CategoryVisualKey, CatalogCategorySectionTheme>>;

const DEFAULT_SECTION_THEME: CatalogCategorySectionTheme = {
  surface: "#e8eae3",
  accent: "#64766d",
};

export function categorySectionThemeFor(slug: string): CatalogCategorySectionTheme {
  const alias = Object.prototype.hasOwnProperty.call(CATEGORY_VISUAL_ALIASES, slug)
    ? CATEGORY_VISUAL_ALIASES[slug]
    : undefined;
  const key = alias ?? slug;
  return Object.prototype.hasOwnProperty.call(CATALOG_CATEGORY_SECTION_THEMES, key)
    ? CATALOG_CATEGORY_SECTION_THEMES[key as CategoryVisualKey]
    : DEFAULT_SECTION_THEME;
}

/** Only visual variables; API names, counts, game order and covers are untouched. */
export function categorySectionStyleFor(slug: string): CSSProperties {
  const theme = categorySectionThemeFor(slug);
  return {
    "--category-section-bg": theme.surface,
    "--category-section-accent": theme.accent,
    "--category-section-ink": "#183c34",
  };
}
