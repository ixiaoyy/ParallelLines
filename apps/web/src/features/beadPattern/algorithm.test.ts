import { describe, expect, it } from "vitest";

import { generatePattern } from "./algorithm";
import { getMaterialCounts } from "./model";
import { ARTKAL_S_COLORS, type BeadColor } from "./palette";

/** 将测试色卡明确写成真实颜色，避免测试预期依赖算法内部距离公式。 */
function color(code: string, rgb: readonly [number, number, number]): BeadColor {
  return { code, name: code, rgb, hex: `#${rgb.map((value) => value.toString(16).padStart(2, "0")).join("")}` };
}

const BASIC = [
  color("white", [255, 255, 255]),
  color("black", [0, 0, 0]),
  color("red", [255, 0, 0]),
  color("green", [0, 255, 0]),
  color("blue", [0, 0, 255]),
  color("gray", [128, 128, 128]),
] as const;

/** 将显式像素样本排列为 RGBA；所有测试透明度都由调用方给定。 */
function pixels(rows: ReadonlyArray<readonly [number, number, number, number]>): Uint8ClampedArray {
  return new Uint8ClampedArray(rows.flat());
}

describe("拼豆确定性颜色转换", () => {
  it("透明与白豆分开，128 阈值包含可见格，半透明黑色不混白", () => {
    const data = pixels([
      [255, 255, 255, 0],
      [255, 255, 255, 127],
      [255, 255, 255, 128],
      [0, 0, 0, 128],
      [255, 255, 255, 255],
    ]);
    const before = data.slice();
    const result = generatePattern(5, 1, data, 6, BASIC);
    expect(result.cells).toEqual([null, null, "white", "black", "white"]);
    expect(getMaterialCounts(result, BASIC).map((row) => [row.color.code, row.count])).toEqual([["white", 2], ["black", 1]]);
    expect(data).toEqual(before);
  });

  it("全透明图仍保留尺寸，所有格为空且用量为零", () => {
    const result = generatePattern(3, 2, new Uint8ClampedArray(24), 1, BASIC);
    expect(result).toEqual({ width: 3, height: 2, cells: [null, null, null, null, null, null] });
    expect(getMaterialCounts(result, BASIC)).toEqual([]);
  });

  it("色卡内的精确颜色保留色号，同 RGB 始终使用第一个色号", () => {
    const palette = [...BASIC, color("white-duplicate", [255, 255, 255])];
    const result = generatePattern(2, 1, pixels([[255, 255, 255, 255], [255, 0, 0, 255]]), 6, palette);
    expect(result.cells).toEqual(["white", "red"]);
    expect(generatePattern(1, 1, pixels([[0, 0, 0, 255]]), 1, [color("one", [0, 0, 0]), color("two", [0, 0, 0])]).cells).toEqual(["one"]);
  });

  it.each([1, 2, 8, 16, 24])("真实色卡的复杂样本最多输出 %i 种色，统计合计等于非空格数", (limit) => {
    const data = new Uint8ClampedArray(32 * 32 * 4);
    for (let index = 0; index < 32 * 32; index += 1) {
      data.set([(index * 37) % 256, (index * 71) % 256, (index * 101) % 256, index % 7 === 0 ? 0 : 255], index * 4);
    }
    const result = generatePattern(32, 32, data, limit, ARTKAL_S_COLORS);
    const counts = getMaterialCounts(result, ARTKAL_S_COLORS);
    expect(counts.length).toBeLessThanOrEqual(limit);
    expect(counts.reduce((sum, row) => sum + row.count, 0)).toBe(877);
    expect(result.cells.filter((code) => code === null)).toHaveLength(147);
  });

  it("重复生成与像素顺序变化得到相同的逐色映射", () => {
    const sample = pixels([
      [255, 0, 0, 255], [255, 0, 0, 255], [0, 255, 0, 255], [0, 0, 255, 255],
      [0, 0, 0, 255], [255, 255, 255, 255], [128, 128, 128, 255], [45, 45, 45, 0],
    ]);
    const result = generatePattern(8, 1, sample, 3, BASIC);
    expect(generatePattern(8, 1, sample, 3, BASIC)).toEqual(result);
    const reverse = new Uint8ClampedArray(sample.length);
    for (let index = 0; index < 8; index += 1) reverse.set(sample.subarray(index * 4, index * 4 + 4), (7 - index) * 4);
    expect(generatePattern(8, 1, reverse, 3, BASIC).cells).toEqual([...result.cells].reverse());
  });

  it("肤色渐变限色后仍保留明暗次序，不把半透明边界变成白边", () => {
    const skin = [
      color("light", [255, 224, 189]),
      color("medium", [220, 163, 123]),
      color("shade", [171, 111, 76]),
      color("dark", [112, 66, 44]),
    ];
    const palette = [...skin, ...BASIC];
    const data = new Uint8ClampedArray(64 * 4);
    for (let index = 0; index < 64; index += 1) {
      const share = index / 63;
      data.set([255 - 143 * share, 224 - 158 * share, 189 - 145 * share, index === 0 ? 128 : 255], index * 4);
    }
    const result = generatePattern(64, 1, data, 4, palette);
    expect(result.cells[0]).toBe("light");
    expect(result.cells[63]).toBe("dark");
    expect(result.cells.every((code) => skin.some((entry) => entry.code === code))).toBe(true);
    const ranks = result.cells.map((code) => skin.findIndex((entry) => entry.code === code));
    expect(ranks).toEqual([...ranks].sort((a, b) => a - b));
  });

  it("最大 128×128 图纸可以处理且不改变非空格数量", () => {
    const data = new Uint8ClampedArray(128 * 128 * 4).fill(255);
    const result = generatePattern(128, 128, data, 16, ARTKAL_S_COLORS);
    expect(result.cells).toHaveLength(16384);
    expect(new Set(result.cells)).toEqual(new Set(["S01"]));
  });

  it.each([
    [0, 1, 1], [129, 1, 1], [1, 129, 1], [1.5, 1, 1], [1, 1, 0], [1, 1, 1.5], [1, 1, 513],
  ])("拒绝无效尺寸或颜色上限 %s/%s/%s", (width, height, limit) => {
    expect(() => generatePattern(width, height, pixels([[0, 0, 0, 255]]), limit, BASIC)).toThrow("invalid_bead_pattern_input");
  });

  it("拒绝错误缓冲区、空色卡、重复色号和非法 RGB", () => {
    expect(() => generatePattern(2, 1, new Uint8ClampedArray(4), 1, BASIC)).toThrow("invalid_bead_pattern_input");
    expect(() => generatePattern(1, 1, new Uint8ClampedArray(4), 1, [])).toThrow("invalid_bead_pattern_input");
    expect(() => generatePattern(1, 1, new Uint8ClampedArray(4), 1, [BASIC[0], BASIC[0]])).toThrow("invalid_bead_palette");
    expect(() => generatePattern(1, 1, new Uint8ClampedArray(4), 1, [color("invalid", [256, 0, 0])])).toThrow("invalid_bead_palette");
  });
});
