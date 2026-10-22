import { MAX_GRID_EDGE, type BeadPattern } from "./model";
import type { BeadColor } from "./palette";

export interface PatternDrawOptions {
  cellSize: number;
  grid?: boolean;
  codes?: boolean;
  highlight?: string | null;
  coordinates?: boolean;
  // 分页图纸沿用完整图纸的坐标，调用方传入从 0 开始的偏移。
  originColumn?: number;
  originRow?: number;
}

export interface PatternLayout {
  cellSize: number;
  offsetX: number;
  offsetY: number;
  width: number;
  height: number;
}

/** 检查图纸尺寸和格数，避免异常图纸触发超大画布或错位导出。 */
export function assertPatternSize(pattern: BeadPattern): void {
  if (!Number.isInteger(pattern.width) || !Number.isInteger(pattern.height)
    || pattern.width < 1 || pattern.height < 1
    || pattern.width > MAX_GRID_EDGE || pattern.height > MAX_GRID_EDGE
    || pattern.cells.length !== pattern.width * pattern.height) {
    throw new Error("invalid_bead_pattern_size");
  }
}

/** 在指定画布绘制图纸并返回真实像素布局；空格不计作白豆，效果图保留透明。 */
export function drawPattern(
  canvas: HTMLCanvasElement,
  pattern: BeadPattern,
  palette: readonly BeadColor[],
  options: PatternDrawOptions,
): PatternLayout {
  assertPatternSize(pattern);
  if (!Number.isFinite(options.cellSize) || options.cellSize < 1 || options.cellSize > 64) {
    throw new Error("invalid_bead_cell_size");
  }
  const cellSize = Math.round(options.cellSize);
  const gutter = options.coordinates ? 32 : 0;
  const layout: PatternLayout = {
    cellSize,
    offsetX: gutter,
    offsetY: gutter,
    width: pattern.width * cellSize + gutter * 2,
    height: pattern.height * cellSize + gutter * 2,
  };
  canvas.width = layout.width;
  canvas.height = layout.height;
  const context = canvas.getContext("2d");
  if (!context) throw new Error("bead_canvas_unavailable");
  context.imageSmoothingEnabled = false;
  const colors = new Map(palette.map((color) => [color.code, color]));

  // 参考图以纸面背景显示坐标；无网格的效果图不填背景，保留原图空白。
  if (options.grid || options.coordinates) {
    context.fillStyle = "#ffffff";
    context.fillRect(0, 0, canvas.width, canvas.height);
  }
  for (let row = 0; row < pattern.height; row += 1) {
    for (let column = 0; column < pattern.width; column += 1) {
      const code = pattern.cells[row * pattern.width + column];
      const x = gutter + column * cellSize;
      const y = gutter + row * cellSize;
      if (code === null) {
        if (options.grid) {
          context.fillStyle = (row + column) % 2 === 0 ? "#f1f5f9" : "#f8fafc";
          context.fillRect(x, y, cellSize, cellSize);
          // 空格的小点仅用于看图；实际白豆仍绘制色号，不会与空格混淆。
          if (cellSize >= 12) {
            context.fillStyle = "#94a3b8";
            context.fillRect(x + Math.floor(cellSize / 2), y + Math.floor(cellSize / 2), 1, 1);
          }
        }
        continue;
      }
      if (typeof code !== "string") throw new Error("invalid_bead_cell");
      const color = colors.get(code);
      if (!color) throw new Error(`unknown_bead_color:${code}`);
      const dimmed = Boolean(options.highlight && code !== options.highlight);
      context.globalAlpha = dimmed ? 0.18 : 1;
      context.fillStyle = color.hex;
      context.fillRect(x, y, cellSize, cellSize);
      context.globalAlpha = 1;
      if (options.codes && cellSize >= 18) {
        context.fillStyle = dimmed ? "#334155" : cellTextColor(color);
        const fontSize = Math.min(12, Math.floor(cellSize / Math.max(2.5, code.length * 0.7)));
        context.font = `600 ${fontSize}px Arial, sans-serif`;
        context.textAlign = "center";
        context.textBaseline = "middle";
        context.fillText(code, x + cellSize / 2, y + cellSize / 2, cellSize - 2);
      }
    }
  }

  if (options.grid) drawGrid(context, pattern, layout, options);
  if (options.coordinates) drawCoordinates(context, pattern, layout, options);
  return layout;
}

/** 用线性亮度选择黑字或白字，使不同豆色上的编号保持足够对比度。 */
function cellTextColor(color: BeadColor): string {
  const channels = color.rgb.map((value) => {
    const channel = value / 255;
    return channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
  });
  const luminance = channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722;
  return (luminance + 0.05) / 0.05 >= 1.05 / (luminance + 0.05) ? "#000000" : "#ffffff";
}

/** 绘制细格线及每十格的定位线；分页时按完整图纸位置延续十格节奏。 */
function drawGrid(
  context: CanvasRenderingContext2D,
  pattern: BeadPattern,
  layout: PatternLayout,
  options: PatternDrawOptions,
): void {
  const { offsetX, offsetY, cellSize } = layout;
  const originColumn = options.originColumn ?? 0;
  const originRow = options.originRow ?? 0;
  for (let column = 0; column <= pattern.width; column += 1) {
    const major = column === 0 || column === pattern.width || (originColumn + column) % 10 === 0;
    context.strokeStyle = major ? "#64748b" : "rgba(71, 85, 105, 0.28)";
    context.lineWidth = major ? 1.2 : 0.6;
    context.beginPath();
    context.moveTo(offsetX + column * cellSize + 0.5, offsetY);
    context.lineTo(offsetX + column * cellSize + 0.5, offsetY + pattern.height * cellSize);
    context.stroke();
  }
  for (let row = 0; row <= pattern.height; row += 1) {
    const major = row === 0 || row === pattern.height || (originRow + row) % 10 === 0;
    context.strokeStyle = major ? "#64748b" : "rgba(71, 85, 105, 0.28)";
    context.lineWidth = major ? 1.2 : 0.6;
    context.beginPath();
    context.moveTo(offsetX, offsetY + row * cellSize + 0.5);
    context.lineTo(offsetX + pattern.width * cellSize, offsetY + row * cellSize + 0.5);
    context.stroke();
  }
}

/** 在网格四边标注从 1 开始的行列号，首尾及每五格保留定位标记。 */
function drawCoordinates(
  context: CanvasRenderingContext2D,
  pattern: BeadPattern,
  layout: PatternLayout,
  options: PatternDrawOptions,
): void {
  const { offsetX, offsetY, cellSize } = layout;
  const originColumn = options.originColumn ?? 0;
  const originRow = options.originRow ?? 0;
  context.fillStyle = "#334155";
  context.font = "11px Arial, sans-serif";
  context.textAlign = "center";
  context.textBaseline = "middle";
  for (let column = 0; column < pattern.width; column += 1) {
    const number = originColumn + column + 1;
    if (column !== 0 && column !== pattern.width - 1 && number % 5 !== 0) continue;
    const x = offsetX + (column + 0.5) * cellSize;
    context.fillText(String(number), x, offsetY / 2);
    context.fillText(String(number), x, offsetY + pattern.height * cellSize + 16);
  }
  for (let row = 0; row < pattern.height; row += 1) {
    const number = originRow + row + 1;
    if (row !== 0 && row !== pattern.height - 1 && number % 5 !== 0) continue;
    const y = offsetY + (row + 0.5) * cellSize;
    context.fillText(String(number), offsetX / 2, y);
    context.fillText(String(number), offsetX + pattern.width * cellSize + 16, y);
  }
}
