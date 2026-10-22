import type { BeadColor } from "./palette";

export interface BeadPattern {
  width: number;
  height: number;
  // null 表示不摆豆子的空格，不能用白色替代。
  cells: Array<string | null>;
}

export interface CropRegion {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface MaterialCount {
  color: BeadColor;
  count: number;
}

export const MAX_GRID_EDGE = 128;
export const MAX_IMAGE_BYTES = 10 * 1024 * 1024;
export const MAX_IMAGE_PIXELS = 20_000_000;

export const BEAD_MESSAGES = {
  type: "请选择 JPG、PNG 或 WebP 图片。",
  size: "图片不能超过 10 MB，请压缩后重试。",
  read: "无法读取这张图片，请换一张图片重试。",
  pixels: "图片分辨率过高，请缩小到 2000 万像素以内后重试。",
  generate: "图纸生成失败，请缩小图纸尺寸后重试。",
  export: "导出失败，请重试。",
  replace: "重新生成将清除当前手动修改，是否继续？",
} as const;

/** 按最终图纸统计材料；忽略空格，未知色号视为数据错误。 */
export function getMaterialCounts(pattern: BeadPattern, palette: readonly BeadColor[]): MaterialCount[] {
  const counts = new Map<string, number>();
  for (const code of pattern.cells) {
    if (code !== null) counts.set(code, (counts.get(code) ?? 0) + 1);
  }
  const colors = new Map(palette.map((color) => [color.code, color]));
  return [...counts].map(([code, count]) => {
    const color = colors.get(code);
    if (!color) throw new Error(`unknown_bead_color:${code}`);
    return { color, count };
  }).sort((a, b) => b.count - a.count || a.color.code.localeCompare(b.color.code, "en", { numeric: true }));
}
