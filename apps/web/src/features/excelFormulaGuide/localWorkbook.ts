import { read, SSF, utils, write, type CellObject, type WorkBook, type WorkSheet } from "xlsx";
import type { DataSheet, LocalWorkbook, OperationResult, PlainCell } from "./localProcessingModel";

export const LOCAL_WORKBOOK_LIMITS = {
  fileBytes: 5 * 1024 * 1024,
  sheets: 10,
  rows: 5_000,
  columns: 50,
  cells: 100_000,
  zipEntries: 1_000,
  expandedBytes: 32 * 1024 * 1024,
} as const;

type DateParts = { y: number; m: number; d: number; H: number; M: number; S: number; u: number };
const ssf = SSF as {
  is_date(format: string): boolean;
  parse_date_code(value: number, options: { date1904: boolean }): DateParts | null;
};
const hasOwn = (value: object, key: string) => Object.prototype.hasOwnProperty.call(value, key);
const messageOf = (error: unknown) => error instanceof Error ? error.message : "无法读取工作表";

/** Check the ZIP directory before expanding a local file; no file is uploaded. */
function checkXlsxPackage(buffer: ArrayBuffer, sourceName: string): void {
  if (!/\.xlsx$/i.test(sourceName)) throw new Error("仅支持 .xlsx 文件，请先在 Excel 中另存为 .xlsx。");
  if (!buffer.byteLength || buffer.byteLength > LOCAL_WORKBOOK_LIMITS.fileBytes) throw new Error("文件为空或超过 5 MiB，请先缩小文件。");
  const bytes = new Uint8Array(buffer);
  const view = new DataView(buffer);
  if (bytes.length < 22 || view.getUint32(0, true) !== 0x04034b50) throw new Error("文件不是有效的 XLSX ZIP 工作簿。");
  let end = -1;
  for (let offset = bytes.length - 22; offset >= Math.max(0, bytes.length - 65_557); offset--) {
    if (view.getUint32(offset, true) === 0x06054b50 && offset + 22 + view.getUint16(offset + 20, true) === bytes.length) {
      end = offset;
      break;
    }
  }
  if (end < 0) throw new Error("XLSX ZIP 目录不完整或文件已损坏。");
  const entries = view.getUint16(end + 10, true);
  const directoryBytes = view.getUint32(end + 12, true);
  const directoryOffset = view.getUint32(end + 16, true);
  if (view.getUint16(end + 4, true) || view.getUint16(end + 6, true)
    || view.getUint16(end + 8, true) !== entries || entries === 0xffff
    || directoryOffset === 0xffffffff || directoryBytes === 0xffffffff
    || entries > LOCAL_WORKBOOK_LIMITS.zipEntries || directoryOffset + directoryBytes !== end) {
    throw new Error("不支持分卷、ZIP64 或过于复杂的工作簿。");
  }
  const names = new Set<string>();
  const decoder = new TextDecoder("utf-8", { fatal: true });
  let offset = directoryOffset;
  let expandedBytes = 0;
  for (let index = 0; index < entries; index++) {
    if (offset + 46 > end || view.getUint32(offset, true) !== 0x02014b50) throw new Error("XLSX ZIP 目录已损坏。");
    const flags = view.getUint16(offset + 8, true);
    const method = view.getUint16(offset + 10, true);
    const compressed = view.getUint32(offset + 20, true);
    const expanded = view.getUint32(offset + 24, true);
    const nameLength = view.getUint16(offset + 28, true);
    const next = offset + 46 + nameLength + view.getUint16(offset + 30, true) + view.getUint16(offset + 32, true);
    const localOffset = view.getUint32(offset + 42, true);
    if (next > end || (flags & 1) || ![0, 8].includes(method) || localOffset + 30 > directoryOffset
      || compressed === 0xffffffff || expanded === 0xffffffff
      || view.getUint32(localOffset, true) !== 0x04034b50) throw new Error("不支持加密或已损坏的 XLSX 文件。");
    const dataStart = localOffset + 30 + view.getUint16(localOffset + 26, true) + view.getUint16(localOffset + 28, true);
    if (dataStart + compressed > directoryOffset) throw new Error("XLSX ZIP 文件内容不完整。");
    let name: string;
    try { name = decoder.decode(bytes.subarray(offset + 46, offset + 46 + nameLength)); }
    catch { throw new Error("XLSX ZIP 文件名编码无效。"); }
    if (names.has(name) || name.startsWith("/") || name.split("/").includes("..")) throw new Error("XLSX ZIP 文件路径无效或重复。");
    names.add(name);
    expandedBytes += expanded;
    if (expandedBytes > LOCAL_WORKBOOK_LIMITS.expandedBytes) throw new Error("工作簿解压后超过 32 MiB，请缩小文件。");
    offset = next;
  }
  if (offset !== end || !names.has("[Content_Types].xml") || !names.has("xl/workbook.xml") || names.has("xl/workbook.bin")) {
    throw new Error("仅支持标准 XLSX 工作簿，不能通过修改扩展名导入其他格式。");
  }
  if ([...names].some(name => /(^|\/)vbaProject\.bin$/i.test(name))) throw new Error("不支持包含 VBA 宏的工作簿，请另存为不含宏的 XLSX。");
}

function sheetBounds(sheet: WorkSheet): { rows: number; columns: number } | null {
  let rows = 0;
  let columns = 0;
  for (const property of ["!ref", "!fullref"]) {
    const reference: unknown = sheet[property];
    if (reference === undefined) continue;
    if (typeof reference !== "string" || !/^[A-Z]+[1-9]\d*(?::[A-Z]+[1-9]\d*)?$/.test(reference)) throw new Error("工作表范围无效。");
    const range = utils.decode_range(reference);
    if (range.s.r > range.e.r || range.s.c > range.e.c) throw new Error("工作表范围无效。");
    rows = Math.max(rows, range.e.r + 1);
    columns = Math.max(columns, range.e.c + 1);
  }
  for (const address of Object.keys(sheet)) {
    if (address.startsWith("!")) continue;
    if (!/^[A-Z]+[1-9]\d*$/.test(address)) throw new Error("工作表包含不支持的单元格地址。");
    const cell = utils.decode_cell(address);
    rows = Math.max(rows, cell.r + 1);
    columns = Math.max(columns, cell.c + 1);
  }
  return rows && columns ? { rows, columns } : null;
}

const pad = (value: number, length = 2) => String(value).padStart(length, "0");
function dateText(value: number, format: string, date1904: boolean): string {
  if (value < 0 || (!date1904 && Math.floor(value) === 60)) throw new Error("含无法可靠表示的 Excel 日期（例如 1900-02-29）。");
  if (/\[(?:h+|m+|s+)\]/i.test(format)) throw new Error("暂不支持累计时长格式，请先转换为普通数值或文本。");
  const parts = ssf.parse_date_code(value, { date1904 });
  if (!parts || !Object.values(parts).every(Number.isFinite)) throw new Error("日期值无效或超出支持范围。");
  const simpleFormat = format.replace(/"[^"]*"|\\.|\[[^\]]*\]/g, "");
  const timeOnly = !/[yd]/i.test(simpleFormat) && /[hs]/i.test(simpleFormat) && !/m{3}/i.test(simpleFormat);
  const fraction = parts.u ? parts.u.toFixed(9).slice(1).replace(/0+$/, "") : "";
  const time = `${pad(parts.H)}:${pad(parts.M)}:${pad(parts.S)}${fraction}`;
  if (timeOnly && value < 1) return time;
  if (parts.y < 1 || parts.y > 9999 || parts.m < 1 || parts.m > 12 || parts.d < 1
    || parts.d > new Date(Date.UTC(parts.y < 100 ? 400 + parts.y : parts.y, parts.m, 0)).getUTCDate()) throw new Error("含无法可靠表示的 Excel 日期。");
  const date = `${pad(parts.y, 4)}-${pad(parts.m)}-${pad(parts.d)}`;
  return parts.H || parts.M || parts.S || parts.u || timeOnly ? `${date} ${time}` : date;
}

function plainCell(cell: unknown, date1904: boolean, warnings: Set<string>): PlainCell {
  if (cell === undefined || cell === null) return null;
  if (typeof cell !== "object" || Array.isArray(cell)) throw new Error("单元格结构无效。");
  const source = cell as Record<string, unknown>;
  if (hasOwn(source, "f") || hasOwn(source, "F") || source.D === true) throw new Error("包含公式或数组公式；请先复制并粘贴为值。");
  if (source.t === "e") throw new Error("包含 Excel 错误单元格；请先修正错误。");
  if (source.t === "z" || source.v === undefined || source.v === null) return null;
  if (source.t === "s" || source.t === "str") {
    if (typeof source.v !== "string") throw new Error("文本单元格内容无效。");
    return source.v;
  }
  if (source.t === "b" && typeof source.v === "boolean") return source.v;
  if (source.t !== "n" || typeof source.v !== "number" || !Number.isFinite(source.v)) throw new Error("包含非有限数字或不支持的单元格类型。");
  const value = source.v;
  if (Number.isInteger(value) && Math.abs(value) >= 1e15) throw new Error("包含超过 15 位的数值整数，原值可能已丢失精度；长编号请使用文本格式。");
  const format = typeof source.z === "string" ? source.z : "General";
  if (ssf.is_date(format)) {
    warnings.add("日期和时间已转换为无时区文本；导出不保留原日期格式。");
    return { date: dateText(value, format, date1904) };
  }
  if (/^0{2,}$/.test(format)) {
    if (!Number.isInteger(value)) throw new Error("补零编号格式包含小数，请先转换为文本。");
    const formatted = typeof source.w === "string" ? source.w : `${value < 0 ? "-" : ""}${String(Math.abs(value)).padStart(format.length, "0")}`;
    if (!/^-?\d+$/.test(formatted)) throw new Error("补零编号无法可靠转换为文本。");
    warnings.add("纯补零格式的编号已按显示值转换为文本，保留前导零。");
    return formatted;
  }
  if (format !== "General" && format !== "0") warnings.add("数值仅保留底层值；货币、百分比和其他显示格式不会导出。");
  return value;
}

export function readLocalWorkbook(buffer: ArrayBuffer, sourceName: string): LocalWorkbook {
  checkXlsxPackage(buffer, sourceName);
  let workbook: WorkBook;
  try {
    workbook = read(buffer, {
      type: "array", cellFormula: true, cellNF: true, cellText: true, cellDates: false,
      cellStyles: true, cellHTML: false, bookVBA: true, sheetRows: LOCAL_WORKBOOK_LIMITS.rows + 1,
    });
  } catch { throw new Error("XLSX 工作簿无法解析，可能已损坏、加密或格式不受支持。"); }
  if (workbook.vbaraw) throw new Error("不支持包含 VBA 宏的工作簿。");
  if (!workbook.SheetNames.length || workbook.SheetNames.length > LOCAL_WORKBOOK_LIMITS.sheets) throw new Error("工作簿必须包含 1–10 张工作表。");
  let totalCells = 0;
  const bounds = workbook.SheetNames.map(name => {
    const sheet = workbook.Sheets[name];
    if (!sheet) throw new Error("工作表内容缺失。");
    const size = sheetBounds(sheet);
    if (size) {
      if (size.rows > LOCAL_WORKBOOK_LIMITS.rows || size.columns > LOCAL_WORKBOOK_LIMITS.columns) throw new Error(`工作表“${name}”超过 5000 行或 50 列，未导入任何数据。`);
      totalCells += size.rows * size.columns;
      if (totalCells > LOCAL_WORKBOOK_LIMITS.cells) throw new Error("工作簿累计表格范围超过 100000 个单元格，未导入任何数据。");
    }
    return size;
  });
  const date1904 = workbook.Workbook?.WBProps?.date1904 === true;
  const sheets: DataSheet[] = workbook.SheetNames.map((name, index) => {
    const sheet = workbook.Sheets[name];
    const size = bounds[index];
    const warnings = new Set<string>();
    try {
      if (!size) throw new Error("工作表为空。");
      if (workbook.Workbook?.Sheets?.[index]?.Hidden) throw new Error("隐藏工作表暂不处理；请先在 Excel 中明确取消隐藏。");
      if (sheet["!merges"]?.length) throw new Error("包含合并单元格；请先取消合并并补齐数据。");
      if (sheet["!rows"]?.some(row => row?.hidden) || sheet["!cols"]?.some(column => column?.hidden)) throw new Error("包含隐藏行或列；请先明确取消隐藏或删除后再导入。");
      const rows = Array.from({ length: size.rows }, (_, row) =>
        Array.from({ length: size.columns }, (_, column) => {
          try { return plainCell(sheet[utils.encode_cell({ r: row, c: column })] as unknown, date1904, warnings); }
          catch (error) { throw new Error(`${utils.encode_cell({ r: row, c: column })}：${messageOf(error)}`); }
        }));
      if (!rows.some(row => row.some(cell => cell !== null && cell !== ""))) throw new Error("工作表没有可处理的数据。");
      return { name, rows, warnings: [...warnings] };
    } catch (error) { return { name, rows: [], warnings: [], blockedReason: messageOf(error) }; }
  });
  if (!sheets.some(sheet => !sheet.blockedReason)) throw new Error(`没有可处理的普通值工作表。${sheets.map(sheet => `${sheet.name}：${sheet.blockedReason}`).join("；")}`);
  return { sourceName, sheets };
}

function outputCell(value: PlainCell): CellObject | undefined {
  if (value === null) return undefined;
  if (typeof value === "string") {
    if (value.length > 32_767) throw new Error("文本超过 Excel 单元格长度上限。");
    return { t: "s", v: value };
  }
  if (typeof value === "boolean") return { t: "b", v: value };
  if (typeof value === "number") {
    if (!Number.isFinite(value) || (Number.isInteger(value) && Math.abs(value) >= 1e15)) throw new Error("结果包含无法安全导出的数字，请改用文本。");
    return { t: "n", v: value };
  }
  if (typeof value === "object" && typeof value.date === "string") return outputCell(value.date);
  throw new Error("结果包含不支持的值。");
}

function valueSheet(rows: PlainCell[][], columns?: number): WorkSheet {
  const columnCount = columns ?? Math.max(1, ...rows.map(row => row.length));
  if (rows.length > LOCAL_WORKBOOK_LIMITS.rows || columnCount > LOCAL_WORKBOOK_LIMITS.columns
    || rows.length * columnCount > LOCAL_WORKBOOK_LIMITS.cells) throw new Error("结果超过本地导出上限。");
  const sheet: WorkSheet = {};
  rows.forEach((row, r) => {
    if (row.length > columnCount) throw new Error("结果列数不一致。");
    row.forEach((value, c) => {
      const cell = outputCell(value);
      if (cell) sheet[utils.encode_cell({ r, c })] = cell;
    });
  });
  if (rows.length) sheet["!ref"] = utils.encode_range({ s: { r: 0, c: 0 }, e: { r: rows.length - 1, c: columnCount - 1 } });
  return sheet;
}

export function writeOperationWorkbook(result: OperationResult, sheetName: string): ArrayBuffer {
  if (result.issues.length) throw new Error("仍有异常未解决，不能导出结果，请先检查异常行。");
  if ((result.kind === "sum" || result.kind === "count") && !result.aggregate) throw new Error("汇总结果不完整，不能导出。");
  if (!Number.isInteger(result.columnCount) || result.columnCount < 1) throw new Error("结果列数无效。");
  const workbook = utils.book_new();
  const cleanName = sheetName.replace(/[\\/:*?\[\]]/g, "_").replace(/^'+|'+$/g, "").trim().slice(0, 31) || "处理结果";
  const resultName = cleanName === "汇总" && result.aggregate ? "处理结果" : cleanName;
  const resultRows = result.headers ? [result.headers, ...result.rows] : result.rows;
  const summaryRows: PlainCell[][] | undefined = result.aggregate ? [
      ["项目", "值"], ["操作", result.kind === "sum" ? "单条件求和" : "单条件计数"], ["来源工作表", sheetName],
      ["结果", result.aggregate.exportCell], ["匹配记录", result.summary.matchedRows],
      ["参与求和的数字记录", result.summary.usedNumericRows], ["跳过的空值记录", result.summary.blankNumericRows],
      ["说明", result.aggregate.notice ?? "新文件只保留本次结果的值；不复制原公式、样式、图片或其他工作表。"],
    ] : undefined;
  const summaryCells = summaryRows ? summaryRows.length * Math.max(...summaryRows.map(row => row.length)) : 0;
  if (resultRows.length * result.columnCount + summaryCells > LOCAL_WORKBOOK_LIMITS.cells) {
    throw new Error("导出整本累计超过 100000 个单元格（汇总页也计入），请缩小结果后再导出。");
  }
  utils.book_append_sheet(workbook, valueSheet(resultRows, result.columnCount), resultName);
  if (summaryRows) utils.book_append_sheet(workbook, valueSheet(summaryRows), "汇总");
  const output: unknown = write(workbook, { type: "array", bookType: "xlsx", compression: true });
  if (output instanceof ArrayBuffer) return output;
  if (output instanceof Uint8Array) return new Uint8Array(output).buffer;
  throw new Error("结果文件生成失败。");
}
