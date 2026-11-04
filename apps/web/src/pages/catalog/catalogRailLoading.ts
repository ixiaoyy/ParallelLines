import { arrangeMixedCovers } from "./catalogCoverComposition";
import type { CatalogCategoryComposition } from "./catalogCategoryThemes";

export interface CatalogRailGeometry {
  viewport: number;
  gap: number;
  peek: number;
  normal: number;
  lead: number;
  portrait: number;
  panorama: number;
}

/** 根据当前横向位置恢复尾端需求；零位置不自发追加，不依赖历史最大滚动距离。 */
export function catalogRailTailTarget(geometry: CatalogRailGeometry, scrollLeft: number, contentRight: number): number | null {
  return scrollLeft > .5 && contentRight - scrollLeft - geometry.viewport <= geometry.normal + geometry.gap
    ? scrollLeft + geometry.viewport * 1.85 : null;
}

/** 将像素缺口转为有上限的请求量；mixed 只补完整三元组，不使用固定每类条数。 */
export function catalogRailRequestLimit(geometry: CatalogRailGeometry, deficit: number, pending: number, remaining: number, composition?: CatalogCategoryComposition, firstItem = false): number {
  // 后续项目方向未知时先按普通卡片估算，不能用最窄竖版把整排一次过取成多屏。
  // 真正的竖版占比由响应后卡片 rect 体现；调用方仅对剩余像素缺口有限补页。
  const width = composition === "panorama" ? geometry.panorama : geometry.normal;
  if (!(width > 0) || !(geometry.viewport > 0) || remaining <= 0) return 0;
  const leadExtra = firstItem && composition !== "mixed" && composition !== "balanced" && composition !== "panorama"
    ? Math.max(0, geometry.lead - geometry.normal) : 0;
  const count = Math.max(1, Math.ceil((Math.max(0, deficit - leadExtra) + geometry.gap) / (width + geometry.gap)));
  const grouped = composition === "mixed" ? Math.max(1, Math.ceil(count / 3) * 3 - pending) : count;
  return Math.min(60, remaining, grouped);
}

/** 仅排列新完整三元组，保留已提交顺序；页尾不足三项只在 EOF 提交。 */
export function stableCatalogRailPrefix<T extends { id: string }>(items: readonly T[], previousIds: readonly string[], ended: boolean, composition: CatalogCategoryComposition | undefined, aspect: (item: T) => number | undefined, priority: (item: T) => number): T[] {
  const byId = new Map(items.map((item) => [item.id, item]));
  const retained = previousIds.flatMap((id) => byId.has(id) ? [byId.get(id)!] : []);
  const known = new Set(retained.map((item) => item.id));
  const fresh = [...byId.values()].filter((item) => !known.has(item.id));
  if (composition !== "mixed") return [...retained, ...fresh];
  const length = ended ? fresh.length : Math.floor(fresh.length / 3) * 3;
  return [...retained, ...arrangeMixedCovers(fresh.slice(0, length), aspect, priority)];
}
