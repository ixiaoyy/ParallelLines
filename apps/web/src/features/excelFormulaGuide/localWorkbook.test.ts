import { describe, expect, it } from "vitest";
import { read, utils, write, type WorkBook, type WorkSheet } from "xlsx";
import { LOCAL_WORKBOOK_LIMITS, readLocalWorkbook, writeOperationWorkbook } from "./localWorkbook";
import type { OperationResult, PlainCell } from "./localProcessingModel";

function file(sheets: Record<string, WorkSheet>, edit?: (book: WorkBook) => void): ArrayBuffer {
  const book = utils.book_new();
  Object.entries(sheets).forEach(([name, sheet]) => utils.book_append_sheet(book, sheet, name));
  edit?.(book);
  return write(book, { type: "array", bookType: "xlsx", compression: true }) as ArrayBuffer;
}
const table = (rows: (string | number | boolean | null)[][]) => utils.aoa_to_sheet(rows);
const basic = () => table([["姓名", "金额"], ["甲", 1.25], ["乙", 2.5]]);
function result(rows: PlainCell[][] = [["001", 1.25, true, null, { date: "2026-10-22" }]]): OperationResult {
  return {
    kind: "clean", headers: ["编号", "金额", "有效", "备注", "日期"], rows,
    rowNumbers: rows.map((_, index) => index + 2), columnCount: 5, issues: [],
    summary: { inputRows: rows.length, outputRows: rows.length, changedCells: 0, removedRows: 0, matchedRows: 0, usedNumericRows: 0, blankNumericRows: 0 },
  };
}
function readFirst(sheet: WorkSheet) { return readLocalWorkbook(file({ 数据: sheet }), "测试.xlsx").sheets[0]; }

describe("readLocalWorkbook ordinary values", () => {
  it("preserves text IDs, numbers, booleans, nulls and leading blank positions", () => {
    const sheet = table([[null, null, null], ["000001", "12345678901234567890", false], [1.25, true, null]]);
    const book = readLocalWorkbook(file({ 数据: sheet, 其他: basic() }), "人工.xlsx");
    expect(book.sourceName).toBe("人工.xlsx");
    expect(book.sheets).toHaveLength(2);
    expect(book.sheets[0].rows).toEqual([[null, null, null], ["000001", "12345678901234567890", false], [1.25, true, null]]);
  });
  it("converts strict numeric zero padding to text with a warning", () => {
    const sheet = table([[123, -12]]);
    sheet.A1.z = "000000";
    sheet.B1.z = "000000";
    const output = readFirst(sheet);
    expect(output.rows).toEqual([["000123", "-000012"]]);
    expect(output.warnings.join()).toContain("前导零");
  });
  it("retains percent underlying numeric values and warns about formatting", () => {
    const sheet = table([[0.25]]);
    sheet.A1.z = "0%";
    expect(readFirst(sheet)).toMatchObject({ rows: [[0.25]], warnings: [expect.stringContaining("底层值")] });
  });
  it("converts 1900 dates and clock times to stable text without timezone shifts", () => {
    const sheet = table([[1, 61.5, 0.25]]);
    sheet.A1.z = "yyyy-mm-dd";
    sheet.B1.z = "yyyy-mm-dd hh:mm:ss";
    sheet.C1.z = "hh:mm:ss";
    expect(readFirst(sheet).rows).toEqual([[{ date: "1900-01-01" }, { date: "1900-03-01 12:00:00" }, { date: "06:00:00" }]]);
  });
  it("uses the workbook 1904 date system", () => {
    const sheet = table([[0, 60]]);
    sheet.A1.z = sheet.B1.z = "yyyy-mm-dd";
    const buffer = file({ 日期: sheet }, book => { book.Workbook = { WBProps: { date1904: true } }; });
    expect(readLocalWorkbook(buffer, "1904.xlsx").sheets[0].rows).toEqual([[{ date: "1904-01-01" }, { date: "1904-03-01" }]]);
  });
});

describe("readLocalWorkbook refuses unsupported structures", () => {
  it.each([
    ["formula", () => ({ A1: { t: "n", v: 2, f: "1+1" }, "!ref": "A1" }), "公式"],
    ["uncached formula", () => ({ A1: { t: "n", f: "1+1" }, "!ref": "A1" }), "公式"],
    ["array formula", () => ({ A1: { t: "n", v: 2, f: "1+1", F: "A1:A2" }, A2: { t: "n", v: 2, F: "A1:A2" }, "!ref": "A1:A2" }), "公式"],
    ["error", () => ({ A1: { t: "e", v: 7 }, "!ref": "A1" }), "错误"],
    ["large number", () => table([[1234567890123456]]), "15 位"],
    ["fake leap date", () => ({ A1: { t: "n", v: 60, z: "yyyy-mm-dd" }, "!ref": "A1" }), "1900-02-29"],
    ["invalid date zero", () => ({ A1: { t: "n", v: 0, z: "yyyy-mm-dd" }, "!ref": "A1" }), "日期"],
    ["elapsed time", () => ({ A1: { t: "n", v: 1.5, z: "[h]:mm" }, "!ref": "A1" }), "累计时长"],
    ["merged", () => ({ ...basic(), "!merges": [utils.decode_range("A1:B1")] }), "合并"],
    ["hidden row", () => ({ ...basic(), "!rows": [{ hidden: true }] }), "隐藏行或列"],
    ["hidden column", () => ({ ...basic(), "!cols": [{ hidden: true }] }), "隐藏行或列"],
    ["empty", () => ({}), "空"],
  ] as [string, () => WorkSheet, string][])("blocks %s, while retaining a separate safe sheet", (_label, makeSheet, reason) => {
    const output = readLocalWorkbook(file({ 安全: basic(), 不能处理: makeSheet() }), "混合.xlsx");
    expect(output.sheets[0].blockedReason).toBeUndefined();
    expect(output.sheets[1].blockedReason).toContain(reason);
    expect(output.sheets[1].rows).toEqual([]);
    expect(() => readLocalWorkbook(file({ 不能处理: makeSheet() }), "异常.xlsx")).toThrow("没有可处理");
  });
  it("does not expose hidden worksheets", () => {
    const buffer = file({ 安全: basic(), 隐藏: basic() }, book => { book.Workbook = { Sheets: [{ Hidden: 0 }, { Hidden: 1 }] }; });
    expect(readLocalWorkbook(buffer, "隐藏.xlsx").sheets[1].blockedReason).toContain("隐藏工作表");
  });
  it.each(["input.xls", "input.xlsm", "input.csv", "input.zip"])("refuses %s", name => {
    expect(() => readLocalWorkbook(file({ 数据: basic() }), name)).toThrow("仅支持 .xlsx");
  });
  it("refuses damaged ZIPs and renamed ODS", () => {
    expect(() => readLocalWorkbook(new TextEncoder().encode("a,b\n1,2").buffer, "fake.xlsx")).toThrow("ZIP");
    const valid = new Uint8Array(file({ 数据: basic() }));
    expect(() => readLocalWorkbook(valid.slice(0, -10).buffer, "broken.xlsx")).toThrow("目录");
    const book = utils.book_new();
    utils.book_append_sheet(book, basic(), "数据");
    const ods = write(book, { type: "array", bookType: "ods" }) as ArrayBuffer;
    expect(() => readLocalWorkbook(ods, "renamed.xlsx")).toThrow("标准 XLSX");
  });
  it("rejects VBA content even when extension is xlsx", () => {
    const book = utils.book_new();
    utils.book_append_sheet(book, basic(), "数据");
    book.vbaraw = new Uint8Array([1, 2, 3]);
    const buffer = write(book, { type: "array", bookType: "xlsm", compression: true }) as ArrayBuffer;
    expect(() => readLocalWorkbook(buffer, "renamed.xlsx")).toThrow("VBA");
  });
});

describe("readLocalWorkbook limits", () => {
  it("refuses files over 5 MiB", () => expect(() => readLocalWorkbook(new ArrayBuffer(LOCAL_WORKBOOK_LIMITS.fileBytes + 1), "large.xlsx")).toThrow("5 MiB"));
  it("rejects 11 sheets", () => {
    const sheets = Object.fromEntries(Array.from({ length: 11 }, (_, index) => [`表${index}`, basic()]));
    expect(() => readLocalWorkbook(file(sheets), "sheets.xlsx")).toThrow("1–10");
  });
  it("checks !fullref beyond sheetRows instead of silently truncating", () => {
    const sheet: WorkSheet = { A1: { t: "s", v: "开始" }, A6000: { t: "s", v: "末尾" }, "!ref": "A1:A6000" };
    expect(() => readFirst(sheet)).toThrow("5000 行");
  });
  it("rejects 51 columns", () => expect(() => readFirst({ A1: { t: "s", v: "开始" }, AY1: { t: "s", v: "末尾" }, "!ref": "A1:AY1" })).toThrow("50 列"));
  it("accepts the exact 5000 row limit", () => {
    expect(readFirst({ A1: { t: "n", v: 1 }, A5000: { t: "n", v: 2 }, "!ref": "A1:A5000" }).rows).toHaveLength(5000);
  });
  it("rejects accumulated rectangular cells, including blanks", () => {
    const sheet: WorkSheet = { A1: { t: "n", v: 1 }, AD2000: { t: "n", v: 2 }, "!ref": "A1:AD2000" };
    expect(() => readLocalWorkbook(file({ 一: sheet, 二: sheet }), "large.xlsx")).toThrow("100000");
  });
  it("checks ZIP expanded size before parsing", () => {
    const buffer = file({ 数据: basic() });
    const view = new DataView(buffer);
    for (let offset = 0; offset <= buffer.byteLength - 46; offset++) {
      if (view.getUint32(offset, true) === 0x02014b50) {
        view.setUint32(offset + 24, LOCAL_WORKBOOK_LIMITS.expandedBytes + 1, true);
        break;
      }
    }
    expect(() => readLocalWorkbook(buffer, "zipbomb.xlsx")).toThrow("32 MiB");
  });
});

describe("writeOperationWorkbook", () => {
  it("exports a fresh values workbook and rereads it without changing the input", () => {
    const input = result();
    const original = structuredClone(input);
    const buffer = writeOperationWorkbook(input, "原表");
    const output = readLocalWorkbook(buffer, "结果.xlsx");
    expect(output.sheets.map(sheet => sheet.name)).toEqual(["原表"]);
    expect(output.sheets[0].rows).toEqual([input.headers, ["001", 1.25, true, null, "2026-10-22"]]);
    expect(input).toEqual(original);
    const raw = read(buffer, { type: "array", cellFormula: true, cellNF: true });
    expect(raw.Sheets.原表.A2.t).toBe("s");
    expect(raw.Sheets.原表.B2.t).toBe("n");
    expect(raw.Sheets.原表.C2.t).toBe("b");
    expect(raw.Sheets.原表.E2.t).toBe("s");
    expect(raw.Sheets.原表["!merges"]).toBeUndefined();
  });
  it("exports formula-like user strings as plain text", () => {
    const input = result([["=SUM(A1:A2)", "+CMD", "-1+2", "@SUM(A1)", "12345678901234567890"]]);
    const buffer = writeOperationWorkbook(input, "文本");
    const raw = read(buffer, { type: "array", cellFormula: true });
    for (const address of ["A2", "B2", "C2", "D2", "E2"]) {
      expect(raw.Sheets.文本[address].t).toBe("s");
      expect(raw.Sheets.文本[address].f).toBeUndefined();
    }
    expect(readLocalWorkbook(buffer, "result.xlsx").sheets[0].rows[1]).toEqual(input.rows[0]);
  });
  it.each(["sum", "count"] as const)("exports %s with matched rows plus a separate summary", kind => {
    const input = result([["甲", 0.1, null, null, null], ["甲", 0.2, null, null, null]]);
    input.kind = kind;
    input.summary.matchedRows = 2;
    input.summary.usedNumericRows = kind === "sum" ? 2 : 0;
    input.aggregate = { value: kind === "sum" ? "0.3" : "2", exportCell: kind === "sum" ? 0.3 : 2 };
    const buffer = writeOperationWorkbook(input, "汇总");
    const output = readLocalWorkbook(buffer, "summary.xlsx");
    expect(output.sheets.map(sheet => sheet.name)).toEqual(["处理结果", "汇总"]);
    expect(output.sheets[1].rows[3]).toEqual(["结果", input.aggregate.exportCell]);
  });
  it("keeps precision-protected aggregate strings as text", () => {
    const input = result();
    input.kind = "sum";
    input.aggregate = { value: "1234567890123456.12", exportCell: "1234567890123456.12", notice: "文本保留精度" };
    const raw = read(writeOperationWorkbook(input, "数据"), { type: "array" });
    expect(raw.Sheets.汇总.B4).toMatchObject({ t: "s", v: "1234567890123456.12" });
    expect(raw.Sheets.汇总.B8.v).toBe("文本保留精度");
  });
  it("refuses unresolved issues and incomplete aggregate results", () => {
    const input = result();
    input.issues.push({ row: 2, column: 2, message: "无效金额" });
    expect(() => writeOperationWorkbook(input, "数据")).toThrow("异常");
    input.issues = [];
    input.kind = "sum";
    expect(() => writeOperationWorkbook(input, "数据")).toThrow("不完整");
  });
  it("refuses unsafe numeric results", () => {
    expect(() => writeOperationWorkbook(result([[Infinity]]), "数据")).toThrow("数字");
    expect(() => writeOperationWorkbook(result([[1234567890123456]]), "数据")).toThrow("数字");
  });
  function budgetResult(rowCount: number, columnCount: number): OperationResult {
    const input = result(Array.from({ length: rowCount }, () => Array.from({ length: columnCount }, (_, column) => column)));
    input.headers = null;
    input.columnCount = columnCount;
    input.kind = "count";
    input.summary.matchedRows = rowCount;
    input.aggregate = { value: String(rowCount), exportCell: rowCount };
    return input;
  }
  it("counts the summary sheet in the whole-workbook export cell budget", () => {
    const input = budgetResult(5_000, 20);
    expect(() => writeOperationWorkbook(input, "结果")).toThrow("汇总页也计入");
    expect(() => writeOperationWorkbook(input, "结果")).toThrow("请缩小");
    expect(input.rows).toHaveLength(5_000);
  });
  it("round-trips exactly 100000 cells including the summary sheet", () => {
    const input = budgetResult(4_166, 24); // 99,984 result cells + 16 summary cells.
    const output = readLocalWorkbook(writeOperationWorkbook(input, "结果"), "边界.xlsx");
    expect(output.sheets).toHaveLength(2);
    expect(output.sheets[0].rows).toEqual(input.rows);
    expect(output.sheets[1].rows[3]).toEqual(["结果", 4_166]);
    expect(output.sheets.reduce((total, sheet) => total + sheet.rows.length * sheet.rows[0].length, 0)).toBe(100_000);
  });
});
