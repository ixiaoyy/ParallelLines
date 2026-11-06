import type { CSSProperties } from "vue";
import { CATEGORY_VISUAL_ALIASES, type CategoryVisualKey } from "@/features/catalog/categoryVisuals";

export type CatalogCategoryComposition = "mixed" | "balanced" | "split" | "panorama";

interface CatalogCategorySectionTheme {
  readonly tail?: CategoryVisualKey;
  readonly surface: string;
  readonly ink: string;
  readonly leadScale?: number;
  readonly leadHeightScale?: number;
  readonly singleMaxWidth?: number;
  readonly composition?: CatalogCategoryComposition;
}

/** Composition metadata for real category keys; never creates categories or game lists. */
export const CATALOG_CATEGORY_SECTION_THEMES = {
  action: { surface: "#fff5e9", ink: "#63371b" },
  shooting: { surface: "#f0f5fb", ink: "#264b59" },
  racing: { surface: "#edfaf4", ink: "#265c4a", leadScale: 1.2, leadHeightScale: 1.1 },
  stages: { surface: "#fff1ea", ink: "#9b492b" },
  puzzle: { surface: "#f1f8e8", ink: "#3c632d" },
  rts: { surface: "#f7f4e8", ink: "#5a542b" },
  "tower-defense": { surface: "#f1f4e9", ink: "#47563a" },
  cards: { surface: "#fff1ec", ink: "#823f28" },
  rpg: { surface: "#f2f1fb", ink: "#4d456e", leadScale: 1.2, leadHeightScale: 1.1 },
  simulation: { surface: "#fff8e6", ink: "#765220" },
  casual: { surface: "#fff9e9", ink: "#48260e", composition: "mixed", leadScale: 1.35, leadHeightScale: 1.2 },
  romance: { surface: "#fcf0f3", ink: "#894254" },
  horror: { surface: "#f5efed", ink: "#be241a", composition: "balanced" },
  exploration: { surface: "#edfbf7", ink: "#07523d", composition: "split", leadScale: 1.4, leadHeightScale: 1.15 },
  farming: { surface: "#fffae8", ink: "#8f5104", composition: "panorama", singleMaxWidth: 340 },
} as const satisfies Readonly<Record<CategoryVisualKey, CatalogCategorySectionTheme>>;

const DEFAULT_SECTION_THEME: CatalogCategorySectionTheme = {
  surface: "#f0f8f4", ink: "#204d3d",
};

export function categorySectionThemeFor(slug: string): CatalogCategorySectionTheme {
  const alias = Object.prototype.hasOwnProperty.call(CATEGORY_VISUAL_ALIASES, slug) ? CATEGORY_VISUAL_ALIASES[slug] : undefined;
  const key = alias ?? slug;
  return Object.prototype.hasOwnProperty.call(CATALOG_CATEGORY_SECTION_THEMES, key)
    ? CATALOG_CATEGORY_SECTION_THEMES[key as CategoryVisualKey] : DEFAULT_SECTION_THEME;
}

export function categorySectionStyleFor(slug: string): CSSProperties {
  const theme = categorySectionThemeFor(slug);
  return {
    "--category-section-bg": theme.surface,
    "--category-section-ink": theme.ink,
    "--category-lead-scale": theme.leadScale ?? 1,
    "--category-lead-height-scale": theme.leadHeightScale ?? 1,
    "--category-single-max-width": `${theme.singleMaxWidth ?? 340}px`,
  };
}
