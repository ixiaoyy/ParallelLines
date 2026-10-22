/*!
 * The red-mean weighted RGB distance is adapted from Perler Beads Generator.
 * Copyright (c) 2026 Jett-Wu. MIT License.
 * Source: https://github.com/Jett-Wu/Perler_Beads_Generator/blob/aa360a1d50f9dd3d87a30354960f3f718bd412a4/src/palette.ts
 * Modifications: squared distance, readonly tuples, bounded deterministic palette selection.
 * Full license: ./third-party/Jett-Wu-MIT.txt and /tools/bead-pattern/OPEN_SOURCE.md
 */

import { MAX_GRID_EDGE, type BeadPattern } from "./model";
import type { BeadColor } from "./palette";

type Rgb = readonly [number, number, number];

const MAX_PALETTE_COLORS = 512;

/**
 * 将已按目标网格采样的 RGBA 转成品牌色号；返回的空格为 null。
 * 宽高限 1–128，透明度低于 128 不摆豆；仅读取输入，颜色上限包含所有非空格。
 */
export function generatePattern(
  width: number,
  height: number,
  data: Uint8ClampedArray,
  maxColors: number,
  palette: readonly BeadColor[],
): BeadPattern {
  validateInput(width, height, data, maxColors, palette);

  // 官方色卡可有不同色号共用 RGB；自动匹配始终保留色卡中最先出现的色号。
  const rgbKeys = new Set<number>();
  const colors = palette.filter((color) => {
    const key = colorKey(color.rgb[0], color.rgb[1], color.rgb[2]);
    if (rgbKeys.has(key)) return false;
    rgbKeys.add(key);
    return true;
  });
  const counts = new Uint32Array(colors.length);
  const sampled = new Int16Array(width * height).fill(-1);
  const nearestCache = new Map<number, number>();

  // Canvas 已交付非预乘 RGB；半透明可见格保留其本色，不混入白色背景。
  for (let index = 0; index < sampled.length; index += 1) {
    const offset = index * 4;
    if (data[offset + 3] < 128) continue;
    const rgb: Rgb = [data[offset], data[offset + 1], data[offset + 2]];
    const key = colorKey(rgb[0], rgb[1], rgb[2]);
    let nearest = nearestCache.get(key);
    if (nearest === undefined) {
      nearest = nearestColorIndex(rgb, colors);
      nearestCache.set(key, nearest);
    }
    sampled[index] = nearest;
    counts[nearest] += 1;
  }

  const used = colors.map((_, index) => index).filter((index) => counts[index] > 0);
  if (used.length <= maxColors) {
    return { width, height, cells: Array.from(sampled, (index) => index < 0 ? null : colors[index].code) };
  }

  const selected = selectPaletteColors(used, counts, colors, maxColors);
  const selectedColors = selected.map((index) => colors[index]);
  const limitedCache = new Map<number, string>();
  const cells: Array<string | null> = Array.from({ length: sampled.length }, () => null);

  // 限色后重新匹配原采样色，避免把第一次匹配的误差再传递到最终图纸。
  for (let index = 0; index < sampled.length; index += 1) {
    if (sampled[index] < 0) continue;
    const offset = index * 4;
    const rgb: Rgb = [data[offset], data[offset + 1], data[offset + 2]];
    const key = colorKey(rgb[0], rgb[1], rgb[2]);
    let code = limitedCache.get(key);
    if (code === undefined) {
      code = selectedColors[nearestColorIndex(rgb, selectedColors)].code;
      limitedCache.set(key, code);
    }
    cells[index] = code;
  }
  return { width, height, cells };
}

/** 校验网格、缓冲区和色卡边界；失败抛内部错误，由页面统一显示已确认的失败提示。 */
function validateInput(
  width: number,
  height: number,
  data: Uint8ClampedArray,
  maxColors: number,
  palette: readonly BeadColor[],
): void {
  if (
    !Number.isInteger(width) || width < 1 || width > MAX_GRID_EDGE
    || !Number.isInteger(height) || height < 1 || height > MAX_GRID_EDGE
    || !(data instanceof Uint8ClampedArray) || data.length !== width * height * 4
    || !Number.isInteger(maxColors) || maxColors < 1 || maxColors > MAX_PALETTE_COLORS
    || !Array.isArray(palette) || palette.length < 1 || palette.length > MAX_PALETTE_COLORS
  ) throw new Error("invalid_bead_pattern_input");

  const codes = new Set<string>();
  for (const color of palette) {
    if (
      !color || typeof color.code !== "string" || !color.code.trim() || codes.has(color.code)
      || !Array.isArray(color.rgb) || color.rgb.length !== 3
      || color.rgb.some((channel: number) => !Number.isInteger(channel) || channel < 0 || channel > 255)
    ) throw new Error("invalid_bead_palette");
    codes.add(color.code);
  }
}

/** 将三个 8 位颜色分量组合成无碰撞缓存键；透明度由格子是否保留单独处理。 */
function colorKey(r: number, g: number, b: number): number {
  return (r << 16) | (g << 8) | b;
}

/** 返回候选色中的最近项；距离相同时保留输入顺序最靠前的一项。 */
function nearestColorIndex(rgb: Rgb, colors: readonly BeadColor[]): number {
  let best = 0;
  let bestDistance = Number.POSITIVE_INFINITY;
  for (let index = 0; index < colors.length; index += 1) {
    const distance = perceptualDistanceSquared(rgb, colors[index].rgb);
    if (distance < bestDistance) {
      best = index;
      bestDistance = distance;
    }
  }
  return best;
}

/** 沿用 MIT 上游的红色均值加权 RGB 色差；返回平方值以省去比较所不需的平方根。 */
function perceptualDistanceSquared(a: Rgb, b: Rgb): number {
  const redMean = (a[0] + b[0]) / 2;
  const r = a[0] - b[0];
  const g = a[1] - b[1];
  const blue = a[2] - b[2];
  return (2 + redMean / 256) * r * r + 4 * g * g + (2 + (255 - redMean) / 256) * blue * blue;
}

/**
 * 从已命中的品牌色中选择至多 limit 种色，每轮最大化按颗数加权的色差改善。
 * 最多执行 limit 轮；所有并列选择按原色卡顺序处理，保证重复生成和像素重排的稳定性。
 */
function selectPaletteColors(
  used: readonly number[],
  counts: Uint32Array,
  colors: readonly BeadColor[],
  limit: number,
): number[] {
  const size = used.length;
  const distances = new Float64Array(size * size);

  // 矩阵仅覆盖色卡中实际命中的颜色，规模最多 512×512，与原照片尺寸无关。
  for (let first = 0; first < size; first += 1) {
    for (let second = first + 1; second < size; second += 1) {
      const distance = perceptualDistanceSquared(colors[used[first]].rgb, colors[used[second]].rgb);
      distances[first * size + second] = distance;
      distances[second * size + first] = distance;
    }
  }

  // 第一色取整体加权误差最小的实际色号；单色图也不会生成色卡之外的平均色。
  let firstChoice = 0;
  let firstLoss = Number.POSITIVE_INFINITY;
  for (let candidate = 0; candidate < size; candidate += 1) {
    let loss = 0;
    for (let index = 0; index < size; index += 1) {
      loss += counts[used[index]] * distances[index * size + candidate];
    }
    if (loss < firstLoss) {
      firstChoice = candidate;
      firstLoss = loss;
    }
  }
  const selected = [firstChoice];
  const chosen = new Uint8Array(size);
  chosen[firstChoice] = 1;
  const closest = Float64Array.from({ length: size }, (_, index) => distances[index * size + firstChoice]);

  // 新颜色只在确实降低误差时加入；数量达标或无改善即终止。
  while (selected.length < limit) {
    let next = -1;
    let bestImprovement = 0;
    for (let candidate = 0; candidate < size; candidate += 1) {
      if (chosen[candidate]) continue;
      let improvement = 0;
      for (let index = 0; index < size; index += 1) {
        improvement += counts[used[index]] * Math.max(0, closest[index] - distances[index * size + candidate]);
      }
      if (improvement > bestImprovement) {
        next = candidate;
        bestImprovement = improvement;
      }
    }
    if (next < 0) break;
    chosen[next] = 1;
    selected.push(next);
    for (let index = 0; index < size; index += 1) {
      closest[index] = Math.min(closest[index], distances[index * size + next]);
    }
  }
  return selected.map((index) => used[index]).sort((a, b) => a - b);
}
