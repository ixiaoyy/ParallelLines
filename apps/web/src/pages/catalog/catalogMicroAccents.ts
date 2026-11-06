import { staticAssetUrl } from "@/shared/assets/staticAssets";

interface Sprite { src: string; sourceWidth: number; sourceHeight: number; box: readonly [number, number, number, number] }
const atlas = staticAssetUrl("/catalog/2026-10-30-micro/folklore-micro-objects-atlas.webp");
const micro = (box: Sprite["box"]): Sprite => ({ src: atlas, sourceWidth: 1254, sourceHeight: 1254, box });
const old = (path: string, box: Sprite["box"]): Sprite => ({ src: staticAssetUrl(path), sourceWidth: 1024, sourceHeight: 1536, box });

// Actual measured bounds include transparent safety margins, never equal-grid cuts.
export const CATALOG_MICRO_SPRITES = {
  cloud: micro([32, 137, 323, 125]), star: micro([429, 124, 116, 129]),
  sun: micro([701, 92, 196, 194]), drop: micro([1043, 79, 125, 207]),
  ring: micro([54, 371, 227, 228]), black: micro([390, 416, 190, 129]),
  white: micro([706, 421, 184, 126]), flag: micro([1017, 341, 231, 283]),
  card: micro([87, 673, 159, 255]), knot: micro([391, 650, 183, 295]),
  coin: micro([677, 681, 227, 232]), ash: micro([1019, 655, 184, 286]),
  ember: micro([126, 984, 110, 208]), rice: micro([433, 983, 100, 209]),
  kite: old("/catalog/jade-folklore-v1/atlas-c.webp", [530, 10, 260, 192]),
  petal: old("/catalog/2026-10-29-ui/story-tails-c.webp", [168, 257, 25, 18]),
  flower: old("/catalog/2026-10-29-ui/story-tails-c.webp", [157, 1442, 18, 15]),
} as const satisfies Record<string, Sprite>;

type Motif = keyof typeof CATALOG_MICRO_SPRITES;
const themes: Readonly<Record<string, readonly Motif[]>> = {
  action: ["cloud", "star", "star"],
  shooting: ["sun", "star", "star"],
  racing: ["drop", "drop", "drop"],
  stages: ["drop", "star", "star"],
  puzzle: ["ring", "flower", "flower"],
  rts: ["black", "white", "black", "white"],
  "tower-defense": ["flag", "star", "star"],
  cards: ["card", "knot", "card"],
  rpg: ["knot", "flower", "flower"],
  simulation: ["coin", "knot", "coin"],
  casual: ["kite", "petal", "star", "petal"],
  romance: ["petal", "petal", "flower"],
  horror: ["ash", "ember", "ash"],
  exploration: ["petal", "star", "petal"],
  farming: ["rice", "flower", "rice"],
};

/** 为真实分类返回原有微物及其标题空隙内的稳定相对位置。 */
export function microAccentsFor(slug: string) {
  // 点缀只分布在标题与操作间的空隙，窄屏缩放间距，不盖住标题。
  const seed = [...slug].reduce((value, char) => (value * 31 + char.charCodeAt(0)) >>> 0, 7);
  const motifs = Object.prototype.hasOwnProperty.call(themes, slug) ? themes[slug]! : [];
  return motifs.map((kind, index) => ({
    kind, sprite: CATALOG_MICRO_SPRITES[kind],
    rotation: ((seed + index * 13) % 25) - 12,
    x: `${100 * (index + .5) / motifs.length}%`,
    y: `${24 + (seed + index * 17) % 53}%`,
  }));
}
