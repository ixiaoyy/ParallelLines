import { arrangeMixedCovers } from "./catalogCoverComposition";
import type { CatalogCategoryComposition } from "./catalogCategoryThemes";

export interface CatalogRailGeometry {
  viewport: number;
  gap: number;
  peek: number;
  estimatedWidth: number;
}

/** 根据当前横向位置恢复尾端需求；零位置不自发追加，不依赖历史最大滚动距离。 */
export function catalogRailTailTarget(geometry: CatalogRailGeometry, scrollLeft: number, contentRight: number): number | null {
  return scrollLeft > .5 && contentRight - scrollLeft - geometry.viewport <= geometry.estimatedWidth + geometry.gap
    ? scrollLeft + geometry.viewport * 1.85 : null;
}

/** 将像素缺口按已展示卡的平均宽度估算为请求量；混排仍需补齐三元组。 */
export function catalogRailRequestLimit(geometry: CatalogRailGeometry, deficit: number, pending: number, remaining: number, composition?: CatalogCategoryComposition, observedWidth?: number): number {
  // 首屏还没有真实卡宽时用探针估算；窄图较多时按已加载内容修正下一批。
  const width = observedWidth && observedWidth > 0 ? observedWidth : geometry.estimatedWidth;
  if (!(width > 0) || !(geometry.viewport > 0) || remaining <= 0) return 0;
  const count = Math.max(1, Math.ceil((Math.max(0, deficit) + geometry.gap) / (width + geometry.gap)));
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
