import type { CatalogCategory } from "./model";

export interface CategoryVisualTheme {
  /** Internal art direction only; category labels always come from the API. */
  readonly motif: string;
  readonly ink: string;
  readonly wash: string;
}

export interface CategoryAtlasBounds {
  readonly x: number;
  readonly y: number;
  readonly width: number;
  readonly height: number;
}

export type CategoryArtwork =
  | {
      readonly kind: "atlas";
      readonly src: string;
      readonly sourceWidth: number;
      readonly sourceHeight: number;
      /** Pixel bounds measured from the actual atlas, never an assumed grid. */
      readonly bounds: CategoryAtlasBounds;
    }
  | {
      readonly kind: "image";
      readonly src: string;
      readonly aspectRatio?: number;
    };

export interface CatalogCategoryVisual {
  readonly key: string;
  readonly ink: string;
  readonly wash: string;
  readonly artwork?: CategoryArtwork;
}

/** Art metadata for existing category keys; this registry never creates categories. */
export const CATEGORY_VISUAL_THEMES = {
  action: {
    motif: "悟空舞棒",
    ink: "#244e3f",
    wash: "rgba(160, 91, 68, 0.07)",
  },
  shooting: {
    motif: "后羿引弓射日",
    ink: "#244e3f",
    wash: "rgba(167, 129, 64, 0.07)",
  },
  racing: {
    motif: "龙舟争渡",
    ink: "#244e3f",
    wash: "rgba(72, 126, 130, 0.07)",
  },
  stages: {
    motif: "鲤鱼跃龙门",
    ink: "#244e3f",
    wash: "rgba(167, 112, 79, 0.07)",
  },
  puzzle: {
    motif: "白狐抱九连环",
    ink: "#244e3f",
    wash: "rgba(117, 137, 103, 0.07)",
  },
  rts: {
    motif: "弈秋落子",
    ink: "#244e3f",
    wash: "rgba(94, 118, 110, 0.07)",
  },
  "tower-defense": {
    motif: "守将一夫当关",
    ink: "#244e3f",
    wash: "rgba(125, 126, 108, 0.07)",
  },
  cards: {
    motif: "水浒叶子牌",
    ink: "#244e3f",
    wash: "rgba(149, 110, 89, 0.07)",
  },
  rpg: {
    motif: "木兰披甲抱盔",
    ink: "#244e3f",
    wash: "rgba(121, 126, 141, 0.07)",
  },
  simulation: {
    motif: "货郎挑担",
    ink: "#244e3f",
    wash: "rgba(160, 134, 92, 0.07)",
  },
  casual: {
    motif: "小童放纸鸢",
    ink: "#244e3f",
    wash: "rgba(105, 145, 131, 0.07)",
  },
  romance: {
    motif: "牛郎织女鹊桥相会",
    ink: "#244e3f",
    wash: "rgba(157, 117, 139, 0.07)",
  },
  horror: {
    motif: "红盖头花嫁新娘提灯",
    ink: "#244e3f",
    wash: "rgba(139, 96, 98, 0.07)",
  },
  exploration: {
    motif: "渔人拨桃花探洞",
    ink: "#244e3f",
    wash: "rgba(99, 137, 122, 0.07)",
  },
  farming: {
    motif: "牧童骑牛指杏花",
    ink: "#244e3f",
    wash: "rgba(133, 143, 99, 0.07)",
  },
} as const satisfies Readonly<Record<string, CategoryVisualTheme>>;

export type CategoryVisualKey = keyof typeof CATEGORY_VISUAL_THEMES;

/** Add explicit old-slug aliases here when a category key changes; never infer from its title. */
export const CATEGORY_VISUAL_ALIASES: Readonly<Record<string, CategoryVisualKey>> = {};

/** Populate only after real source images and measured pixel bounds are available. */
const atlasA = { kind: "atlas", src: "/catalog/jade-folklore-v1/atlas-a.png", sourceWidth: 972, sourceHeight: 1619 } as const;
const atlasB = { kind: "atlas", src: "/catalog/jade-folklore-v1/atlas-b.png", sourceWidth: 887, sourceHeight: 1774 } as const;
const atlasC = { kind: "atlas", src: "/catalog/jade-folklore-v1/atlas-c.png", sourceWidth: 1024, sourceHeight: 1536 } as const;
export const CATEGORY_ARTWORK: Readonly<Partial<Record<CategoryVisualKey, CategoryArtwork>>> = {
  action: { ...atlasA, bounds: { x: 175, y: 15, width: 625, height: 316 } },
  shooting: { ...atlasA, bounds: { x: 150, y: 336, width: 675, height: 369 } },
  racing: { ...atlasA, bounds: { x: 155, y: 714, width: 660, height: 282 } },
  stages: { ...atlasA, bounds: { x: 245, y: 1000, width: 515, height: 309 } },
  puzzle: { ...atlasA, bounds: { x: 250, y: 1310, width: 455, height: 300 } },
  rts: { ...atlasB, bounds: { x: 261, y: 92, width: 368, height: 245 } },
  "tower-defense": { ...atlasB, bounds: { x: 267, y: 428, width: 390, height: 270 } },
  cards: { ...atlasB, bounds: { x: 214, y: 753, width: 460, height: 276 } },
  rpg: { ...atlasB, bounds: { x: 251, y: 1069, width: 366, height: 286 } },
  simulation: { ...atlasB, bounds: { x: 247, y: 1414, width: 403, height: 316 } },
  casual: { ...atlasC, bounds: { x: 280, y: 10, width: 500, height: 290 } },
  romance: { ...atlasC, bounds: { x: 310, y: 325, width: 415, height: 325 } },
  horror: { ...atlasC, bounds: { x: 395, y: 650, width: 230, height: 290 } },
  exploration: { ...atlasC, bounds: { x: 330, y: 945, width: 450, height: 290 } },
  farming: { ...atlasC, bounds: { x: 280, y: 1240, width: 530, height: 285 } },
};

const CUSTOM_ART_INK = "#244e3f";
const CUSTOM_ART_WASH = "rgba(72, 126, 105, 0.07)";

function isCategoryVisualKey(value: string): value is CategoryVisualKey {
  return Object.prototype.hasOwnProperty.call(CATEGORY_VISUAL_THEMES, value);
}

export function categoryVisualFor(
  category: Pick<CatalogCategory, "slug" | "iconUrl">,
): CatalogCategoryVisual | undefined {
  const alias = Object.prototype.hasOwnProperty.call(CATEGORY_VISUAL_ALIASES, category.slug)
    ? CATEGORY_VISUAL_ALIASES[category.slug]
    : undefined;
  const key = isCategoryVisualKey(category.slug) ? category.slug : alias;
  const theme = key ? CATEGORY_VISUAL_THEMES[key] : undefined;
  if (!theme && !category.iconUrl) return undefined;

  // iconUrl is already sanitized by the catalog model and is an explicit custom-art override.
  const artwork: CategoryArtwork | undefined = category.iconUrl
    ? { kind: "image", src: category.iconUrl }
    : key ? CATEGORY_ARTWORK[key] : undefined;

  return {
    key: key ?? category.slug,
    ink: theme?.ink ?? CUSTOM_ART_INK,
    wash: theme?.wash ?? CUSTOM_ART_WASH,
    ...(artwork ? { artwork } : {}),
  };
}
