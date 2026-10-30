import type { CategoryArtwork } from "@/features/catalog/categoryVisuals";
import { staticAssetUrl } from "@/shared/assets/staticAssets";

export type CatalogAccentKind = "leaves" | "branch-paper" | "compass";
export interface CatalogCategoryAccent {
  readonly kind: CatalogAccentKind;
  readonly placement: "heading" | "card-corner";
  readonly artwork: CategoryArtwork;
  /** Theme calligraphy only, never a game quality/popularity claim. */
  readonly caption?: string;
}

// Only supplied, inspected raster assets enter this registry; no placeholders.
const accents: Readonly<Record<string, CatalogCategoryAccent>> = {
  horror: {
    kind: "branch-paper", placement: "heading", caption: "夜游",
    artwork: { kind: "image", src: staticAssetUrl("/catalog/2026-10-30-folklore/horror-plum-paper-tags-transparent.png"), aspectRatio: 1605 / 980 },
  },
  exploration: {
    kind: "compass", placement: "card-corner", caption: "寻迹",
    artwork: { kind: "atlas", src: staticAssetUrl("/catalog/2026-10-30-folklore/exploration-brass-compass-transparent.png"), sourceWidth: 1145, sourceHeight: 1374, bounds: { x: 165, y: 84, width: 816, height: 1139 } },
  },
};

export function categoryAccentFor(slug: string): CatalogCategoryAccent | undefined {
  return Object.prototype.hasOwnProperty.call(accents, slug) ? accents[slug] : undefined;
}
