import { staticAssetUrl } from "@/shared/assets/staticAssets";

interface Sprite { src: string; sourceWidth: number; sourceHeight: number; box: readonly [number, number, number, number]; width: number }
const atlas = staticAssetUrl("/catalog/2026-10-30-micro/folklore-micro-objects-atlas.png");
const micro = (box: Sprite["box"], width: number): Sprite => ({ src: atlas, sourceWidth: 1254, sourceHeight: 1254, box, width });
const old = (path: string, box: Sprite["box"], width: number): Sprite => ({ src: staticAssetUrl(path), sourceWidth: 1024, sourceHeight: 1536, box, width });

// Actual measured bounds include transparent safety margins, never equal-grid cuts.
export const CATALOG_MICRO_SPRITES = {
  cloud: micro([32, 137, 323, 125], 16), star: micro([429, 124, 116, 129], 8),
  sun: micro([701, 92, 196, 194], 12), drop: micro([1043, 79, 125, 207], 7),
  ring: micro([54, 371, 227, 228], 12), black: micro([390, 416, 190, 129], 10),
  white: micro([706, 421, 184, 126], 10), flag: micro([1017, 341, 231, 283], 11),
  card: micro([87, 673, 159, 255], 9), knot: micro([391, 650, 183, 295], 8),
  coin: micro([677, 681, 227, 232], 11), ash: micro([1019, 655, 184, 286], 6),
  ember: micro([126, 984, 110, 208], 6), rice: micro([433, 983, 100, 209], 6),
  kite: old("/catalog/jade-folklore-v1/atlas-c.png", [530, 10, 260, 192], 20),
  petal: old("/catalog/2026-10-29-ui/story-tails-c.png", [168, 257, 25, 18], 12),
  flower: old("/catalog/2026-10-29-ui/story-tails-c.png", [157, 1442, 18, 15], 10),
} as const satisfies Record<string, Sprite>;

type Motif = keyof typeof CATALOG_MICRO_SPRITES;
interface Accent { kind: Motif; left?: string; right?: string; top?: string; bottom?: string }
const at = (kind: Motif, left: string, top: string): Accent => ({ kind, left, top });
const low = (kind: Motif, left: string, bottom: string): Accent => ({ kind, left, bottom });

// Authored spaces around each real category's main artwork, not around game cards.
const themes: Readonly<Record<string, readonly Accent[]>> = {
  action: [low("cloud", "150px", "18px"), at("star", "68%", "34px"), low("star", "85%", "20px")],
  shooting: [low("sun", "145px", "18px"), at("star", "36%", "28px"), low("star", "40%", "25px")],
  racing: [low("drop", "55px", "18px"), at("drop", "122px", "24px"), at("drop", "82%", "34px")],
  stages: [low("drop", "148px", "18px"), at("star", "45%", "26px"), low("star", "25%", "28px")],
  puzzle: [low("ring", "32px", "18px"), at("flower", "65%", "30px"), low("flower", "82%", "18px")],
  rts: [low("black", "150px", "18px"), at("white", "74%", "28px"), low("black", "86%", "28px"), low("white", "120px", "34px")],
  "tower-defense": [low("flag", "140px", "18px"), at("star", "36%", "26px"), low("star", "88%", "25px")],
  cards: [low("card", "140px", "18px"), at("knot", "74%", "32px"), low("card", "90%", "25px")],
  rpg: [low("knot", "32px", "18px"), at("flower", "36%", "36px"), low("flower", "92%", "18px")],
  simulation: [low("coin", "38px", "18px"), at("knot", "84%", "28px"), low("coin", "92%", "20px")],
  casual: [low("kite", "36px", "18px"), at("petal", "65%", "50px"), low("star", "82%", "24px"), at("petal", "86%", "57px")],
  romance: [low("petal", "36px", "18px"), at("petal", "72%", "36px"), low("flower", "88%", "22px")],
  horror: [low("ash", "22px", "16px"), at("ember", "220px", "22px"), low("ash", "240px", "18px")],
  exploration: [at("petal", "26px", "80px"), at("star", "82%", "24px"), low("petal", "90%", "24px")],
  farming: [low("rice", "145px", "18px"), at("flower", "38%", "24px"), low("rice", "55%", "25px")],
};

export function microAccentsFor(slug: string) {
  // Stable category-key seed varies small rotations/mobile anchors; no runtime randomness.
  const seed = [...slug].reduce((value, char) => (value * 31 + char.charCodeAt(0)) >>> 0, 7);
  return (themes[slug] ?? []).map((accent, index) => ({
    ...accent, sprite: CATALOG_MICRO_SPRITES[accent.kind],
    rotation: ((seed + index * 13) % 25) - 12,
    mobileLeft: `${index === 0 ? 8 + seed % 9 : 39 + seed % 6}px`,
    mobileBottom: `${index === 0 ? 14 + seed % 5 : 24 + seed % 6}px`,
  }));
}
