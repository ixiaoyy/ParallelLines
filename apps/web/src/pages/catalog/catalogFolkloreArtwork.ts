import type { CategoryArtwork } from "@/features/catalog/categoryVisuals";
import { CATEGORY_VISUAL_ALIASES } from "@/features/catalog/categoryVisuals";
import { staticAssetUrl } from "@/shared/assets/staticAssets";

/** Art metadata only. Category names, membership and games always come from the API. */
const artwork: Readonly<Record<string, CategoryArtwork>> = {
  horror: { kind: "image", src: staticAssetUrl("/catalog/2026-10-30-folklore/horror-bride-lantern-transparent.png"), aspectRatio: 1891 / 831 },
  casual: { kind: "atlas", src: staticAssetUrl("/catalog/2026-10-30-folklore/fox-pinwheel-transparent.png"), sourceWidth: 2170, sourceHeight: 725, bounds: { x: 248, y: 124, width: 1701, height: 488 } },
  exploration: { kind: "atlas", src: staticAssetUrl("/catalog/2026-10-30-folklore/exploration-scroll-transparent.png"), sourceWidth: 2174, sourceHeight: 723, bounds: { x: 52, y: 121, width: 2059, height: 479 } },
  farming: { kind: "atlas", src: staticAssetUrl("/catalog/2026-10-30-folklore/buffalo-boy-rice-transparent.png"), sourceWidth: 2191, sourceHeight: 718, bounds: { x: 102, y: 38, width: 2049, height: 660 } },
};

export function folkloreArtworkFor(slug: string): CategoryArtwork | undefined {
  const key = Object.prototype.hasOwnProperty.call(CATEGORY_VISUAL_ALIASES, slug) ? CATEGORY_VISUAL_ALIASES[slug] : slug;
  return Object.prototype.hasOwnProperty.call(artwork, key) ? artwork[key] : undefined;
}
