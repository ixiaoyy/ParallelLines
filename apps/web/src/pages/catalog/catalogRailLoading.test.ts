import { describe, expect, it } from "vitest";
import { catalogRailRequestLimit, catalogRailTailTarget, stableCatalogRailPrefix, type CatalogRailGeometry } from "./catalogRailLoading";

const geometry: CatalogRailGeometry = { viewport: 600, gap: 4, peek: 20, normal: 120, lead: 168, portrait: 58, panorama: 192 };
const item = (id: string, aspect: number | undefined = 1.8, heat = 1): { id: string; aspect: number | undefined; heat: number } => ({ id, aspect, heat });
const aspect = (project: ReturnType<typeof item>) => project.aspect;
const heat = (project: ReturnType<typeof item>) => project.heat;

describe("按真实几何请求分类页", () => {
  it("near重入恢复当前尾端需求，回滚后不受历史最大位置限制，初始零位置不连拉", () => {
    const mobile = { ...geometry, viewport: 342, normal: 157 };
    expect(catalogRailTailTarget(mobile, 0, 378)).toBeNull();
    expect(catalogRailTailTarget(mobile, 942, 1284)).toBeCloseTo(1574.7);
    expect(catalogRailTailTarget(mobile, 100, 442)).toBeCloseTo(732.7);
    expect(catalogRailTailTarget(mobile, 942, 1606)).toBeNull();
  });
  it("宽度和卡片尺寸改变时请求量随之变化，不固定每类条数", () => {
    const small = catalogRailRequestLimit(geometry, 620, 0, 100, "balanced");
    const wide = catalogRailRequestLimit({ ...geometry, viewport: 1400 }, 1420, 0, 100, "balanced");
    expect(wide).toBeGreaterThan(small);
    expect(catalogRailRequestLimit({ ...geometry, normal: 200 }, 620, 0, 100, "balanced")).toBeLessThan(small);
  });
  it("考虑首张lead、全景卡片和混合竖版的真实宽度", () => {
    expect(catalogRailRequestLimit(geometry, 500, 0, 100, "split", true)).toBe(4);
    expect(catalogRailRequestLimit(geometry, 500, 0, 100, "balanced", true)).toBe(5);
    expect(catalogRailRequestLimit(geometry, 620, 0, 100, "panorama")).toBe(4);
    expect(catalogRailRequestLimit(geometry, 620, 0, 100, "mixed") % 3).toBe(0);
    expect(catalogRailRequestLimit(geometry, 620, 2, 100, "mixed") + 2).toBe(catalogRailRequestLimit(geometry, 620, 0, 100, "mixed"));
  });
  it("零宽/空分类不请求，单项目和协议上限截断请求量", () => {
    expect(catalogRailRequestLimit({ ...geometry, viewport: 0 }, 620, 0, 100)).toBe(0);
    expect(catalogRailRequestLimit(geometry, 620, 0, 0)).toBe(0);
    expect(catalogRailRequestLimit(geometry, 620, 0, 1, "mixed")).toBe(1);
    expect(catalogRailRequestLimit(geometry, 100_000, 0, 1000, "mixed")).toBe(60);
  });
  it("mixed首批按普通卡片估算且只为三元组补齐，不用最窄竖版预取多屏", () => {
    const mobile = { ...geometry, viewport: 341, normal: 157, lead: 157, portrait: 56 };
    const desktop = { ...geometry, viewport: 1320, normal: 182, lead: 245.7, portrait: 88.4 };
    expect(catalogRailRequestLimit(mobile, mobile.viewport + 20, 0, 100, "mixed", true)).toBe(3);
    expect(catalogRailRequestLimit(desktop, desktop.viewport + 20, 0, 100, "mixed", true)).toBe(9);
    expect(catalogRailRequestLimit(desktop, 100, 0, 100, "mixed")).toBe(3);
  });
});

describe("分类分页的稳定三元组", () => {
  it("跨页缓冲不完整三元组；EOF提交真实尾段", () => {
    const input = [item("portrait", .6), item("wide", 2), item("wide-hot", 2, 7), item("tail")];
    expect(stableCatalogRailPrefix(input.slice(0, 2), [], false, "mixed", aspect, heat)).toEqual([]);
    const first = stableCatalogRailPrefix(input, [], false, "mixed", aspect, heat);
    expect(first.map((project) => project.id)).toEqual(["wide-hot", "wide", "portrait"]);
    expect(stableCatalogRailPrefix(input, first.map((project) => project.id), true, "mixed", aspect, heat).map((project) => project.id))
      .toEqual(["wide-hot", "wide", "portrait", "tail"]);
  });
  it("后续图片比例或热度迟到时不重排已提交前缀，同时更新真实统计", () => {
    const first = [{ ...item("one"), aspect: undefined }, item("two", 2), item("three", .6)];
    const committed = stableCatalogRailPrefix(first, [], false, "mixed", aspect, heat);
    const changed = [item("one", 2, 99), first[1]!, first[2]!, item("next-portrait", .6), item("next-wide", 2), item("next-hot", 2, 5)];
    const next = stableCatalogRailPrefix(changed, committed.map((project) => project.id), false, "mixed", aspect, heat);
    expect(next.slice(0, 3).map((project) => project.id)).toEqual(["one", "two", "three"]);
    expect(next[0]!.heat).toBe(99);
    expect(next.slice(3).map((project) => project.id)).toEqual(["next-hot", "next-wide", "next-portrait"]);
  });
  it("重复项目只提交一次，下架项目不留在已显示前缀", () => {
    const one = item("one"); const two = item("two");
    expect(stableCatalogRailPrefix([one, one, two], ["removed", "one"], true, "balanced", aspect, heat)).toEqual([one, two]);
    expect(stableCatalogRailPrefix([one], [], true, "mixed", aspect, heat)).toEqual([one]);
  });
});
