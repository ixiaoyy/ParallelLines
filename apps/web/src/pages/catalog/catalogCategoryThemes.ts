import type { CSSProperties } from "vue";
import { CATEGORY_VISUAL_ALIASES, type CategoryVisualKey } from "@/features/catalog/categoryVisuals";

export type CatalogCategoryComposition = "mixed" | "balanced" | "split" | "panorama";

interface CatalogCategorySectionTheme {
  readonly tail?: CategoryVisualKey;
  readonly surface: string;
  readonly ink: string;
  readonly artWidth: number;
  readonly artHeight: number;
  readonly headingHeight: number;
  readonly left?: string;
  readonly right?: string;
  readonly leadScale?: number;
  readonly leadHeightScale?: number;
  readonly singleMaxWidth?: number;
  readonly composition?: CatalogCategoryComposition;
}

/** Composition metadata for real category keys; never creates categories or game lists. */
export const CATALOG_CATEGORY_SECTION_THEMES = {
  action: { surface: "#fff5e9", ink: "#63371b", artWidth: 235, artHeight: 112, headingHeight: 105, left: "23%" },
  shooting: { surface: "#f0f5fb", ink: "#264b59", artWidth: 196, artHeight: 126, headingHeight: 112, right: "19%" },
  racing: { surface: "#edfaf4", ink: "#265c4a", artWidth: 350, artHeight: 105, headingHeight: 96, left: "18%", leadScale: 1.2, leadHeightScale: 1.1 },
  stages: { surface: "#fff1ea", ink: "#9b492b", artWidth: 210, artHeight: 125, headingHeight: 114, right: "12%" },
  puzzle: { surface: "#f1f8e8", ink: "#3c632d", artWidth: 250, artHeight: 102, headingHeight: 94, left: "105px" },
  rts: { surface: "#f7f4e8", ink: "#5a542b", artWidth: 220, artHeight: 124, headingHeight: 110, left: "37%" },
  "tower-defense": { surface: "#f1f4e9", ink: "#47563a", artWidth: 185, artHeight: 134, headingHeight: 120, right: "20%" },
  cards: { surface: "#fff1ec", ink: "#823f28", artWidth: 270, artHeight: 114, headingHeight: 102, left: "29%" },
  rpg: { surface: "#f2f1fb", ink: "#4d456e", artWidth: 195, artHeight: 138, headingHeight: 122, right: "20%", leadScale: 1.2, leadHeightScale: 1.1 },
  simulation: { surface: "#fff8e6", ink: "#765220", artWidth: 315, artHeight: 111, headingHeight: 103, left: "28%" },
  casual: { surface: "#fff9e9", ink: "#48260e", artWidth: 300, artHeight: 90, headingHeight: 86, left: "96px", composition: "mixed", leadScale: 1.35, leadHeightScale: 1.2 },
  romance: { surface: "#fcf0f3", ink: "#894254", artWidth: 340, artHeight: 122, headingHeight: 111, left: "24%" },
  horror: { surface: "#f5efed", ink: "#be241a", artWidth: 270, artHeight: 118, headingHeight: 90, left: "38%", composition: "balanced" },
  exploration: { surface: "#edfbf7", ink: "#07523d", artWidth: 490, artHeight: 114, headingHeight: 92, left: "108px", composition: "split", leadScale: 1.4, leadHeightScale: 1.15 },
  farming: { surface: "#fffae8", ink: "#8f5104", artWidth: 300, artHeight: 92, headingHeight: 82, right: "0px", composition: "panorama", singleMaxWidth: 340 },
} as const satisfies Readonly<Record<CategoryVisualKey, CatalogCategorySectionTheme>>;

const DEFAULT_SECTION_THEME: CatalogCategorySectionTheme = {
  surface: "#f0f8f4", ink: "#204d3d", artWidth: 240, artHeight: 105, headingHeight: 98, left: "30%",
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
    "--category-section-accent": theme.ink,
    "--category-art-left": theme.left ?? "auto",
    "--category-art-right": theme.right ?? "auto",
    "--catalog-art-max-width": `${theme.artWidth}px`,
    "--catalog-art-height": `${theme.artHeight}px`,
    "--category-heading-height": `${theme.headingHeight}px`,
    "--category-lead-scale": theme.leadScale ?? 1,
    "--category-lead-height-scale": theme.leadHeightScale ?? 1,
    "--category-single-max-width": `${theme.singleMaxWidth ?? 340}px`,
  };
}
