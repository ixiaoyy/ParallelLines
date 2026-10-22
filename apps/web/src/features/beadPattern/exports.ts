import { getMaterialCounts, type BeadPattern, type MaterialCount } from "./model";
import type { BeadColor } from "./palette";
import { assertPatternSize, drawPattern } from "./render";

const BRAND_LABEL = "Artkal S 系列 5 mm";
const COLOR_NOTICE = "色号对应上述系列；屏幕与打印颜色仅供参考，请以实际豆子为准。";
const CHART_NOTICE = "一格一颗豆；带点的空格不摆豆。图纸用于数格参考，不是等比例垫板模板。";
const PRINT_COLUMNS = 32;
const PRINT_ROWS = 40;
let disposeActivePrint: (() => void) | null = null;

export interface PrintTile {
  pattern: BeadPattern;
  column: number;
  row: number;
  index: number;
  total: number;
}

/** 将最终图纸按 A4 可读范围分块；坐标保留完整图纸偏移，不遗漏边缘格子。 */
export function getPrintTiles(pattern: BeadPattern): PrintTile[] {
  assertPatternSize(pattern);
  const tiles: PrintTile[] = [];
  const total = Math.ceil(pattern.width / PRINT_COLUMNS) * Math.ceil(pattern.height / PRINT_ROWS);
  for (let row = 0; row < pattern.height; row += PRINT_ROWS) {
    for (let column = 0; column < pattern.width; column += PRINT_COLUMNS) {
      const width = Math.min(PRINT_COLUMNS, pattern.width - column);
      const height = Math.min(PRINT_ROWS, pattern.height - row);
      const cells: Array<string | null> = [];
      for (let tileRow = 0; tileRow < height; tileRow += 1) {
        const start = (row + tileRow) * pattern.width + column;
        cells.push(...pattern.cells.slice(start, start + width));
      }
      tiles.push({ pattern: { width, height, cells }, column, row, index: tiles.length + 1, total });
    }
  }
  return tiles;
}

/** 将最终网格用量编码为可由 Excel 打开的 CSV；空格不计入数量。 */
export function createMaterialsCsv(pattern: BeadPattern, palette: readonly BeadColor[]): string {
  assertPatternSize(pattern);
  const counts = getMaterialCounts(pattern, palette);
  const rows: Array<Array<string | number>> = [
    ["品牌系列", "色号", "参考颜色", "数量（颗）"],
    ...counts.map(({ color, count }) => [BRAND_LABEL, color.code, color.hex, count]),
    ["合计", "", "", counts.reduce((total, item) => total + item.count, 0)],
    ["说明", COLOR_NOTICE, "", ""],
    ["图纸格数", `${pattern.width} × ${pattern.height}`, "", ""],
  ];
  return `\uFEFF${rows.map((row) => row.map(csvCell).join(",")).join("\r\n")}\r\n`;
}

/** 下载用量清单；仅生成本地文件，不向服务器发送图片或图纸。 */
export function downloadMaterialsCsv(pattern: BeadPattern, palette: readonly BeadColor[]): void {
  downloadBlob(new Blob([createMaterialsCsv(pattern, palette)], { type: "text/csv;charset=utf-8" }), "拼豆材料清单.csv");
}

/** 导出透明效果图或包含网格、色号及材料清单的图纸 PNG。 */
export async function downloadPatternPng(
  pattern: BeadPattern,
  palette: readonly BeadColor[],
  kind: "preview" | "chart",
): Promise<void> {
  assertPatternSize(pattern);
  const patternCanvas = document.createElement("canvas");
  drawPattern(patternCanvas, pattern, palette, {
    cellSize: kind === "preview" ? 12 : 28,
    grid: kind === "chart",
    codes: kind === "chart",
    coordinates: kind === "chart",
  });
  const output = kind === "chart"
    ? composeChart(patternCanvas, pattern, getMaterialCounts(pattern, palette))
    : patternCanvas;
  // 拼接后先释放原网格画布，避免大图导出同时持有两份完整像素缓冲。
  if (output !== patternCanvas) {
    patternCanvas.width = 0;
    patternCanvas.height = 0;
  }
  const blob = await new Promise<Blob>((resolve, reject) => {
    output.toBlob((result) => result ? resolve(result) : reject(new Error("bead_png_export_failed")), "image/png");
  });
  downloadBlob(blob, kind === "chart" ? "拼豆图纸.png" : "拼豆效果图.png");
  // PNG 编码结束后释放大画布，连续导出不会累计保留像素缓冲。
  patternCanvas.width = 0;
  patternCanvas.height = 0;
  if (output !== patternCanvas) {
    output.width = 0;
    output.height = 0;
  }
}

/** 生成独立 A4 打印页并唤起浏览器打印；返回表示已发起打印，不代表用户完成打印。 */
export async function printPattern(pattern: BeadPattern, palette: readonly BeadColor[]): Promise<void> {
  assertPatternSize(pattern);
  const counts = getMaterialCounts(pattern, palette);
  const tiles = getPrintTiles(pattern);
  disposeActivePrint?.();
  const frame = document.createElement("iframe");
  frame.title = "拼豆图纸打印预览";
  frame.setAttribute("aria-hidden", "true");
  frame.style.cssText = "position:fixed;left:-10000px;top:0;width:210mm;height:297mm;border:0;";
  document.body.append(frame);
  const printDocument = frame.contentDocument;
  const printWindow = frame.contentWindow;
  if (!printDocument || !printWindow) {
    frame.remove();
    throw new Error("bead_print_frame_unavailable");
  }
  let cleanupTimer = 0;
  const cleanup = () => {
    window.clearTimeout(cleanupTimer);
    frame.remove();
    window.removeEventListener("pagehide", cleanup);
    if (disposeActivePrint === cleanup) disposeActivePrint = null;
  };
  disposeActivePrint = cleanup;
  try {
    printDocument.title = "拼豆图纸";
    printDocument.documentElement.lang = "zh-CN";
    const style = printDocument.createElement("style");
    style.textContent = PRINT_STYLES;
    printDocument.head.append(style);
    const images: HTMLImageElement[] = [];
    for (const tile of tiles) {
      const page = printDocument.createElement("section");
      page.className = "print-page";
      appendText(printDocument, page, "h1", `拼豆图纸 · 第 ${tile.index} / ${tile.total} 块`);
      appendText(printDocument, page, "p", `${BRAND_LABEL} · 列 ${tile.column + 1}–${tile.column + tile.pattern.width} / 行 ${tile.row + 1}–${tile.row + tile.pattern.height}`);
      const canvas = document.createElement("canvas");
      drawPattern(canvas, tile.pattern, palette, {
        cellSize: 28, grid: true, codes: true, coordinates: true,
        originColumn: tile.column, originRow: tile.row,
      });
      const image = printDocument.createElement("img");
      image.className = "pattern-image";
      image.alt = `第 ${tile.index} 块拼豆图纸`;
      // 将图纸作为图片打印，不依赖浏览器是否开启背景颜色打印。
      image.src = canvas.toDataURL("image/png");
      image.style.width = `${canvas.width / 28 * 4.5}mm`;
      page.append(image);
      images.push(image);
      appendText(printDocument, page, "p", CHART_NOTICE, "note");
      appendText(printDocument, page, "p", "材料清单见末页。", "note");
      printDocument.body.append(page);
      canvas.width = 0;
      canvas.height = 0;
    }
    appendPrintMaterials(printDocument, pattern, counts);
    // 等待嵌入的图纸图片可用后再打印，避免打印预览中出现空白图。
    await Promise.all(images.map((image) => waitForPrintImage(image)));
    printWindow.addEventListener("afterprint", cleanup, { once: true });
    window.addEventListener("pagehide", cleanup, { once: true });
    cleanupTimer = window.setTimeout(cleanup, 180_000);
    printWindow.focus();
    printWindow.print();
  } catch (error) {
    cleanup();
    throw error;
  }
}

/** 拼接图纸标题和多列材料清单，输出足够宽的独立图片以免小图标题截断。 */
function composeChart(patternCanvas: HTMLCanvasElement, pattern: BeadPattern, counts: MaterialCount[]): HTMLCanvasElement {
  const width = Math.max(800, patternCanvas.width + 48);
  const columns = Math.min(4, Math.max(2, Math.floor((width - 48) / 250)));
  const listRows = Math.ceil(counts.length / columns);
  const output = document.createElement("canvas");
  output.width = width;
  output.height = 154 + patternCanvas.height + 110 + listRows * 32 + 32;
  const context = output.getContext("2d");
  if (!context) throw new Error("bead_canvas_unavailable");
  context.fillStyle = "#ffffff";
  context.fillRect(0, 0, output.width, output.height);
  context.textAlign = "left";
  context.textBaseline = "top";
  context.fillStyle = "#0f172a";
  context.font = "bold 28px Arial, sans-serif";
  context.fillText("拼豆图纸", 24, 20);
  context.font = "18px Arial, sans-serif";
  const total = counts.reduce((sum, item) => sum + item.count, 0);
  context.fillText(`${BRAND_LABEL} · ${pattern.width} × ${pattern.height} 格 · ${counts.length} 色 · ${total} 颗`, 24, 62);
  context.font = "15px Arial, sans-serif";
  context.fillStyle = "#475569";
  context.fillText(COLOR_NOTICE, 24, 94);
  context.fillText(CHART_NOTICE, 24, 120);
  context.drawImage(patternCanvas, Math.floor((width - patternCanvas.width) / 2), 154);
  const listTop = 154 + patternCanvas.height + 24;
  context.fillStyle = "#0f172a";
  context.font = "bold 22px Arial, sans-serif";
  context.fillText("材料清单", 24, listTop);
  context.font = "16px Arial, sans-serif";
  context.fillStyle = "#475569";
  context.fillText("按最终图纸统计，不含备用豆。", 24, listTop + 34);
  counts.forEach(({ color, count }, index) => {
    const column = Math.floor(index / Math.max(1, listRows));
    const row = index % Math.max(1, listRows);
    const x = 24 + column * ((width - 48) / columns);
    const y = listTop + 70 + row * 32;
    context.fillStyle = color.hex;
    context.fillRect(x, y, 20, 20);
    context.strokeStyle = "#94a3b8";
    context.lineWidth = 1;
    context.strokeRect(x, y, 20, 20);
    context.fillStyle = "#0f172a";
    context.font = "16px Arial, sans-serif";
    context.fillText(`${color.code}    ${count} 颗`, x + 30, y + 2);
  });
  return output;
}

/** 为材料清单显式分页，单页不超过 30 行，避免长清单被截断。 */
function appendPrintMaterials(printDocument: Document, pattern: BeadPattern, counts: MaterialCount[]): void {
  const pageCount = Math.max(1, Math.ceil(counts.length / 30));
  const total = counts.reduce((sum, item) => sum + item.count, 0);
  for (let pageIndex = 0; pageIndex < pageCount; pageIndex += 1) {
    const page = printDocument.createElement("section");
    page.className = "print-page";
    appendText(printDocument, page, "h1", `材料清单 · ${pageIndex + 1} / ${pageCount}`);
    appendText(printDocument, page, "p", `${BRAND_LABEL} · ${pattern.width} × ${pattern.height} 格 · ${counts.length} 色 · ${total} 颗`);
    const table = printDocument.createElement("table");
    const head = printDocument.createElement("thead");
    const headRow = printDocument.createElement("tr");
    ["色号", "参考颜色", "数量（颗）"].forEach((label) => appendText(printDocument, headRow, "th", label));
    head.append(headRow);
    table.append(head);
    const body = printDocument.createElement("tbody");
    for (const { color, count } of counts.slice(pageIndex * 30, (pageIndex + 1) * 30)) {
      const row = printDocument.createElement("tr");
      appendText(printDocument, row, "td", color.code);
      const reference = printDocument.createElement("td");
      const swatch = printDocument.createElement("span");
      swatch.className = "swatch";
      swatch.style.backgroundColor = color.hex;
      reference.append(swatch, printDocument.createTextNode(color.hex));
      row.append(reference);
      appendText(printDocument, row, "td", String(count));
      body.append(row);
    }
    table.append(body);
    page.append(table);
    appendText(printDocument, page, "p", "按最终图纸统计，不含备用豆。空格不需要豆子，白色格使用白豆。", "note");
    appendText(printDocument, page, "p", COLOR_NOTICE, "note");
    printDocument.body.append(page);
  }
}

/** 用 DOM 文本节点插入标题和表格内容，避免将外来色号解释为 HTML。 */
function appendText(printDocument: Document, parent: HTMLElement, tag: string, value: string, className?: string): HTMLElement {
  const element = printDocument.createElement(tag);
  element.textContent = value;
  if (className) element.className = className;
  parent.append(element);
  return element;
}

/** 在限定时间内等候本地数据图片解码，失败向调用方报告以展示统一错误提示。 */
function waitForPrintImage(image: HTMLImageElement): Promise<void> {
  if (image.complete && image.naturalWidth > 0) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const timeout = window.setTimeout(() => finish(new Error("bead_print_image_timeout")), 10_000);
    const finish = (error?: Error) => {
      window.clearTimeout(timeout);
      image.onload = null;
      image.onerror = null;
      if (error) reject(error);
      else resolve();
    };
    image.onload = () => finish();
    image.onerror = () => finish(new Error("bead_print_image_failed"));
  });
}

/** 下载已生成的本地 Blob，并在浏览器取得下载资源后释放对象地址。 */
function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.append(anchor);
  try {
    anchor.click();
  } finally {
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
}

/** 转义 CSV 字段并阻止外来字符串被表格软件解释为公式。 */
function csvCell(value: string | number): string {
  const text = String(value);
  const safe = /^[=+\-@\t\r]/.test(text) ? `'${text}` : text;
  return `"${safe.replace(/"/g, '""')}"`;
}

const PRINT_STYLES = `
@page { size: A4 portrait; margin: 12mm; }
* { box-sizing: border-box; }
html, body { margin: 0; color: #111827; background: #ffffff; font-family: Arial, "Microsoft YaHei", sans-serif; }
.print-page { break-after: page; page-break-after: always; padding: 0; }
.print-page:last-child { break-after: auto; page-break-after: auto; }
h1 { margin: 0 0 3mm; font-size: 17pt; }
p { margin: 0 0 3mm; font-size: 10pt; line-height: 1.5; }
.pattern-image { display: block; max-width: 100%; height: auto; margin: 3mm auto; }
.note { margin-top: 3mm; font-size: 9pt; }
table { width: 100%; margin: 4mm 0; border-collapse: collapse; font-size: 10pt; }
th, td { border-bottom: 0.3mm solid #b8bec7; padding: 1.3mm 2mm; height: 5.6mm; text-align: left; }
tr { break-inside: avoid; page-break-inside: avoid; }
.swatch { display: inline-block; width: 3mm; height: 3mm; margin-right: 2mm; border: 0.2mm solid #64748b; vertical-align: middle; print-color-adjust: exact; -webkit-print-color-adjust: exact; }
`;
