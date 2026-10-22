import { describe, expect, it } from "vitest";

import { createMaterialsCsv, getPrintTiles } from "./exports";
import type { BeadPattern } from "./model";
import type { BeadColor } from "./palette";

const palette: BeadColor[] = [
  { code: "S01", name: "S01", hex: "#ffffff", rgb: [255, 255, 255] },
  { code: "S13", name: "S13", hex: "#000000", rgb: [0, 0, 0] },
];

describe("拼豆导出", () => {
  it("只按最终格子统计白豆和黑豆，不把透明空格计作白豆", () => {
    const pattern: BeadPattern = { width: 3, height: 2, cells: ["S01", null, "S13", "S13", null, "S13"] };
    const csv = createMaterialsCsv(pattern, palette);
    expect(csv.startsWith("\uFEFF")).toBe(true);
    expect(csv).toContain('"S01","#ffffff","1"');
    expect(csv).toContain('"S13","#000000","3"');
    expect(csv).toContain('"合计","","","4"\r\n');
    expect(csv).not.toContain("undefined");
    expect(csv).not.toMatch(/(?<!\r)\n/);
  });

  it("手动擦除和改色后，材料清单使用修改后的数据", () => {
    const pattern: BeadPattern = { width: 2, height: 2, cells: ["S01", "S01", "S13", "S13"] };
    pattern.cells[0] = null;
    pattern.cells[2] = "S01";
    const csv = createMaterialsCsv(pattern, palette);
    expect(csv).toContain('"S01","#ffffff","2"');
    expect(csv).toContain('"S13","#000000","1"');
    expect(csv).toContain('"合计","","","3"');
  });

  it("不静默导出包含未知色号的材料清单", () => {
    expect(() => createMaterialsCsv({ width: 1, height: 1, cells: ["UNKNOWN"] }, palette)).toThrow("unknown_bead_color");
  });

  it("分页后可以按全图坐标重建边缘尺寸不整齐的图纸", () => {
    const width = 65;
    const height = 81;
    const pattern: BeadPattern = {
      width, height,
      cells: Array.from({ length: width * height }, (_, index) => index % 3 === 0 ? null : index % 2 ? "S01" : "S13"),
    };
    const tiles = getPrintTiles(pattern);
    expect(tiles).toHaveLength(9);
    const restored: Array<string | null | undefined> = new Array(width * height);
    const visits = new Array<number>(width * height).fill(0);
    for (const tile of tiles) {
      expect(tile.pattern.width).toBeLessThanOrEqual(32);
      expect(tile.pattern.height).toBeLessThanOrEqual(40);
      for (let row = 0; row < tile.pattern.height; row += 1) {
        for (let column = 0; column < tile.pattern.width; column += 1) {
          const originalIndex = (tile.row + row) * width + tile.column + column;
          restored[originalIndex] = tile.pattern.cells[row * tile.pattern.width + column];
          visits[originalIndex] += 1;
        }
      }
    }
    expect(restored).toEqual(pattern.cells);
    expect(visits.every((count) => count === 1)).toBe(true);
    expect(tiles.at(-1)).toMatchObject({ column: 64, row: 80, index: 9, total: 9, pattern: { width: 1, height: 1 } });
  });

  it("最大图纸分页有上限，空白图纸仍能生成材料清单", () => {
    const pattern = { width: 128, height: 128, cells: new Array<null>(128 * 128).fill(null) };
    expect(getPrintTiles(pattern)).toHaveLength(16);
    expect(createMaterialsCsv(pattern, palette)).toContain('"合计","","","0"');
  });

  it.each([
    { width: 129, height: 1, cells: new Array<null>(129).fill(null) },
    { width: 2, height: 2, cells: [null] },
    { width: 0, height: 1, cells: [] },
  ])("拒绝超范围或格数不完整的图纸", (pattern) => {
    expect(() => getPrintTiles(pattern)).toThrow("invalid_bead_pattern_size");
  });

  it("对外来色号中的引号和公式前缀进行 CSV 转义", () => {
    const color: BeadColor = { code: '=A1,"x"', name: "custom", hex: "#ffffff", rgb: [255, 255, 255] };
    const csv = createMaterialsCsv({ width: 1, height: 1, cells: [color.code] }, [color]);
    expect(csv).toContain('"\'=A1,""x"""');
  });
});
