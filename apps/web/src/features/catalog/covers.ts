import { staticAssetUrl } from "@/shared/assets/staticAssets";
import { CATALOG_COVER_ASPECTS_BY_PATH } from "./coverAspectManifest";
import { getCatalogCoverPath } from "./coverManifest";
import type { CatalogProject } from "./model";

const original = new Set([
  "clock-out", "merge-watermelon", "qin-imperial-factory", "super-mario", "csgo-desert", "infinite-garden",
  "fruit-ninja", "qq-racing", "cf-transport", "pelican-bike", "generals-soldiers",
]);
const second = new Set([
  "yu-gi-oh-destiny-duel", "secondhand-3c-store", "voxel-tides", "sneaky-thief", "liuxin-watermelon",
  "xing-lei-shou-wei", "yongyao-crystal-tower", "zhi-guai-lu", "sanguo-zhengshi", "yeyu-tanglou",
  "non-euclidean-lab", "geodesic-explorer", "hyperbolic-room", "encounter-command-console",
]);

/** 沿用已收录正式封面的版本路径，后台封面仍优先，不猜测不存在的素材。 */
function formalCoverPath(slug: string): string | null {
  if (second.has(slug)) return `/catalog/2026-09-25-v1/covers/${slug}.webp`;
  if (original.has(slug)) return `/catalog/2026-09-24-v1/covers/${slug}.webp`;
  return getCatalogCoverPath(slug);
}

/** 返回真实卡片封面；保留后台上传覆盖和既有 CDN 资源语义。 */
export function catalogCoverUrl(project: CatalogProject): string | null {
  if (project.iconUrl) return project.iconUrl;
  const path = formalCoverPath(project.slug);
  return path ? staticAssetUrl(path) : null;
}

/** 静态正式封面使用实测比例；自定义上传未解码时保持未知，不为布局预加载图片。 */
export function catalogCoverAspect(project: CatalogProject): number | undefined {
  if (project.iconUrl) return undefined;
  const path = formalCoverPath(project.slug);
  return path ? CATALOG_COVER_ASPECTS_BY_PATH[path] : undefined;
}
