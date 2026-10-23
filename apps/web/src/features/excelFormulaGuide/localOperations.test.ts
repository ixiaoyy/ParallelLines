import { describe, expect, it } from "vitest";
import { buildTable, cellText, runOperation } from "./localOperations";
import type { DataSheet, OperationOptions, PlainCell, TableData } from "./localProcessingModel";

const sumOptions: Extract<OperationOptions, { kind: "sum" }> = {
  kind: "sum", conditionColumn: 0, equals: "A", valueColumn: 1,
};
const sheet = (rows: PlainCell[][]): DataSheet => ({ name: "人工无敏感数据", rows, warnings: [] });
const table = (rows: PlainCell[][]): TableData => buildTable(sheet([["分组", "数值"], ...rows]), 1);
const sum = (values: PlainCell[]) => runOperation(table(values.map((value) => ["A", value])), sumOptions);

describe("buildTable", () => {
  it("uses original one-based header and row coordinates, padding without mutation", () => {
    const source = sheet([["说明"], ["姓名", "金额"], ["甲"], ["乙", 2]]);
    const original = structuredClone(source);
    const result = buildTable(source, 2);
    expect(result).toEqual({ headers: ["姓名", "金额"], rows: [["甲", null], ["乙", 2]], rowNumbers: [3, 4], columnCount: 2 });
    expect(source).toEqual(original);
  });
  it("supports no header and a header without following data", () => {
    expect(buildTable(sheet([[1, "001"], [2]]), 0)).toEqual({ headers: null, rows: [[1, "001"], [2, null]], rowNumbers: [1, 2], columnCount: 2 });
    expect(buildTable(sheet([[0, false]]), 1).rows).toEqual([]);
  });
  it.each([-1, 0.5, 2, NaN, Infinity])("rejects invalid header %s", (header) => {
    expect(() => buildTable(sheet([["H"]]), header)).toThrow(Error);
  });
  it("rejects all blank headers but accepts zero and false", () => {
    expect(() => buildTable(sheet([[null, "　\u00a0"]]), 1)).toThrow(/表头/);
    expect(buildTable(sheet([[0, false]]), 1).headers).toEqual([0, false]);
  });
  it("honours blocked sheets and empty-data errors", () => {
    expect(() => buildTable({ ...sheet([["A"]]), blockedReason: "合并单元格不支持" }, 0)).toThrow("合并单元格不支持");
    expect(() => buildTable(sheet([]), 0)).toThrow(Error);
    expect(() => buildTable(sheet([[]]), 0)).toThrow(Error);
  });
  it.each([
    [Array.from({ length: 5_001 }, () => [null])],
    [[Array<PlainCell>(51).fill(null)]],
    [Array.from({ length: 2_501 }, () => Array<PlainCell>(40).fill(null))],
  ])("enforces row, column and rectangular cell limits", (rows) => {
    expect(() => buildTable(sheet(rows), 0)).toThrow(/5000/);
  });
});

describe("clean", () => {
  it("trims Unicode edges, preserves interior whitespace, dates, zero and false", () => {
    const result = runOperation(table([["　甲  乙\u00a0", " 1 "], ["　", null], [0, false], [{ date: "2026-10-22" }, " 已完成 "]]), { kind: "clean", columns: [0, 1], removeBlankRows: true });
    expect(result.rows).toEqual([["甲  乙", "1"], [0, false], [{ date: "2026-10-22" }, "已完成"]]);
    expect(result.rowNumbers).toEqual([2, 4, 5]);
    expect(result.summary).toMatchObject({ inputRows: 4, outputRows: 3, removedRows: 1, changedCells: 3 });
  });
  it("only changes selected columns and keeps blank rows when requested", () => {
    const result = runOperation(table([[" A ", " B "], [" ", null]]), { kind: "clean", columns: [0], removeBlankRows: false });
    expect(result.rows).toEqual([["A", " B "], ["", null]]);
    expect(result.summary.changedCells).toBe(2);
    expect(result.summary.removedRows).toBe(0);
  });
  it.each([[], [-1], [2], [0.5], [NaN]].map((columns) => ({ columns })))("rejects invalid selection $columns", ({ columns }) => {
    expect(() => runOperation(table([[" A ", 1]]), { kind: "clean", columns, removeBlankRows: false })).toThrow(Error);
  });
  it("counts a duplicate selected column once", () => {
    expect(runOperation(table([[" A ", 1]]), { kind: "clean", columns: [0, 0], removeBlankRows: false }).summary.changedCells).toBe(1);
  });
});

describe("dedupe", () => {
  it("keeps the first complete row and original row numbers", () => {
    const result = runOperation(table([["A", 1], ["A", 2], ["B", 3], ["A", 1]]), { kind: "dedupe", columns: [0] });
    expect(result.rows).toEqual([["A", 1], ["B", 3]]);
    expect(result.rowNumbers).toEqual([2, 4]);
    expect(result.summary).toMatchObject({ removedRows: 2, changedCells: 0 });
  });
  it("uses all selected columns with exact case and type matching", () => {
    const result = runOperation(table([["A", 1], ["A", "1"], ["a", 1], [" A", 1], ["A", 1]]), { kind: "dedupe", columns: [0, 1] });
    expect(result.rows).toHaveLength(4);
  });
  it("distinguishes leading-zero strings, numbers, dates and date-looking strings", () => {
    const result = runOperation(table([["001", 1], [1, 2], ["1", 3], ["001", 4], [{ date: "2026-10-22" }, 5], ["2026-10-22", 6]]), { kind: "dedupe", columns: [0] });
    expect(result.rows).toHaveLength(5);
    expect(result.rows[0]).toEqual(["001", 1]);
  });
  it("deduplicates empty keys while retaining typed null, text, false and zero", () => {
    const result = runOperation(table([[null, 1], [null, 2], ["", 3], ["", 4], [false, 5], [0, 6]]), { kind: "dedupe", columns: [0] });
    expect(result.rows).toEqual([[null, 1], ["", 3], [false, 5], [0, 6]]);
    expect(result.summary.removedRows).toBe(2);
  });
  it("rejects empty selections", () => {
    expect(() => runOperation(table([["A", 1]]), { kind: "dedupe", columns: [] })).toThrow(Error);
  });
});

describe("exact decimal sum", () => {
  it("adds decimal numbers without binary floating point drift", () => {
    expect(sum([0.1, 0.2]).aggregate).toEqual({ value: "0.3", exportCell: 0.3 });
    expect(sum(["1.2300", "-1.23", -0]).aggregate).toEqual({ value: "0", exportCell: 0 });
    expect(sum(["+1.", ".25", "-.5"]).aggregate?.value).toBe("0.75");
  });
  it("expands only numeric scientific notation and preserves leading-zero source text", () => {
    expect(sum([1e-7, 1e-7]).aggregate?.value).toBe("0.0000002");
    expect(sum(["0000123.40", "0.60"]).aggregate?.value).toBe("124");
    expect(sum(["1e3"]).aggregate).toBeUndefined();
  });
  it("skips actual empty values, not zero", () => {
    const result = sum([null, "　", "0", 0]);
    expect(result.aggregate?.value).toBe("0");
    expect(result.summary).toMatchObject({ matchedRows: 4, usedNumericRows: 2, blankNumericRows: 2 });
  });
  it("accepts twelve written decimal places but rejects thirteen", () => {
    expect(sum(["0.000000000001", "-0.000000000001"]).aggregate?.value).toBe("0");
    for (const value of ["0.0000000000001", "0.1000000000000", 1e-13]) {
      expect(sum([value]).issues).toHaveLength(1);
      expect(sum([value]).aggregate).toBeUndefined();
    }
  });
  it("rejects unsupported numeric text and never returns a partial total", () => {
    const result = sum(["1,000", "￥100", "10%", "=1+2", "2 + 3", 1]);
    expect(result.issues).toHaveLength(5);
    expect(result.summary.usedNumericRows).toBe(1);
    expect(result.aggregate).toBeUndefined();
  });
  it("reports dates, booleans and non-finite numbers at original coordinates", () => {
    const result = sum([1, false, { date: "2026-10-22" }, NaN, Infinity]);
    expect(result.issues.map(({ row, column }) => ({ row, column }))).toEqual([{ row: 3, column: 2 }, { row: 4, column: 2 }, { row: 5, column: 2 }, { row: 6, column: 2 }]);
    expect(result.aggregate).toBeUndefined();
  });
  it("accepts fifteen-digit numeric integers and rejects sixteen-digit numeric integers", () => {
    expect(sum([999_999_999_999_999]).aggregate?.exportCell).toBe(999_999_999_999_999);
    expect(sum([1_000_000_000_000_000]).issues).toHaveLength(1);
    expect(sum([-1_000_000_000_000_000]).aggregate).toBeUndefined();
  });
  it("preserves longer text numbers exactly and exports unsafe totals as text with notice", () => {
    const result = sum(["1000000000000000", "0.1"]);
    expect(result.aggregate).toMatchObject({ value: "1000000000000000.1", exportCell: "1000000000000000.1" });
    expect(result.aggregate?.notice).toContain("15");
    expect(result.rows[0]?.[1]).toBe("1000000000000000");
  });
  it("limits each input and final total to thirty digits", () => {
    const max = "9".repeat(30);
    expect(sum(["9".repeat(31)]).issues).toHaveLength(1);
    expect(sum([max, 1]).aggregate).toBeUndefined();
    expect(sum([max, 1]).issues[0]?.message).toContain("合计");
    expect(sum([max, `-${max}`]).aggregate?.value).toBe("0");
    expect(sum([max]).aggregate?.exportCell).toBe(max);
  });
  it("matches conditions literally, returns complete matched records and ignores invalid unmatched values", () => {
    const result = runOperation(table([["A", 1], [" A", 2], ["a", 3], ["B", "bad"], ["A", "0.1"]]), sumOptions);
    expect(result.rows).toEqual([["A", 1], ["A", "0.1"]]);
    expect(result.rowNumbers).toEqual([2, 6]);
    expect(result.aggregate?.value).toBe("1.1");
    expect(result.summary).toMatchObject({ matchedRows: 2, outputRows: 2, removedRows: 0 });
  });
  it("uses zero for no matches and all-blank values", () => {
    expect(runOperation(table([["B", "bad"]]), sumOptions).aggregate?.value).toBe("0");
    expect(sum([null, " "]).aggregate?.value).toBe("0");
  });
  it("rejects invalid condition or value columns", () => {
    expect(() => runOperation(table([["A", 1]]), { ...sumOptions, conditionColumn: 2 })).toThrow(Error);
    expect(() => runOperation(table([["A", 1]]), { ...sumOptions, valueColumn: -1 })).toThrow(Error);
  });
});

describe("count and literal display", () => {
  const source = table([[1, 1], ["1", 2], [" 1", 3], [null, 4], ["", 5], [false, 6], [{ date: "2026-10-22" }, 7]]);
  it.each([["1", 2], ["", 2], ["FALSE", 1], ["false", 0], ["2026-10-22", 1], ["*", 0]])("counts exact display condition %s", (equals, expected) => {
    const result = runOperation(source, { kind: "count", conditionColumn: 0, equals });
    expect(result.aggregate).toEqual({ value: String(expected), exportCell: expected });
    expect(result.rows).toHaveLength(expected);
    expect(result.summary.usedNumericRows).toBe(0);
  });
  it("uses explicit text for null, boolean, date and leading-zero strings", () => {
    expect([null, 0, false, true, "001", { date: "2026-10-22" }].map(cellText)).toEqual(["", "0", "FALSE", "TRUE", "001", "2026-10-22"]);
  });
});

describe("immutability and validation", () => {
  it.each(["clean", "dedupe", "sum", "count"] as const)("repeats %s from original data and isolates result objects", (kind) => {
    const source = table([[" A ", " 1 "], ["A", "0.2"], [{ date: "2026-10-22" }, 3]]);
    source.headers = [{ date: "2026-01-01" }, "金额"];
    const snapshot = structuredClone(source);
    const options: OperationOptions = kind === "clean" ? { kind, columns: [0, 1], removeBlankRows: true }
      : kind === "dedupe" ? { kind, columns: [0] }
        : kind === "sum" ? { ...sumOptions, equals: " A " }
          : { kind, conditionColumn: 0, equals: "2026-10-22" };
    const first = runOperation(source, options);
    expect(runOperation(source, options)).toEqual(first);
    expect(source).toEqual(snapshot);
    if (first.headers?.[0] && typeof first.headers[0] === "object") first.headers[0].date = "changed";
    for (const row of first.rows) for (const cell of row) if (cell && typeof cell === "object") cell.date = "changed";
    first.rows[0]?.splice(0, 1, "changed");
    expect(source).toEqual(snapshot);
  });
  it.each([NaN, Infinity, -Infinity, 1e15])("rejects unsafe plain numeric data in clean and dedupe: %s", (value) => {
    for (const options of [{ kind: "clean", columns: [0], removeBlankRows: false }, { kind: "dedupe", columns: [0] }] satisfies OperationOptions[]) {
      expect(() => runOperation(table([["A", value]]), options)).toThrow(/原表/);
    }
  });
  it("rejects malformed table metadata", () => {
    const original = table([["A", 1]]);
    for (const invalid of [{ ...original, rowNumbers: [] }, { ...original, rowNumbers: [0] }, { ...original, rows: [["A"]] }, { ...original, headers: ["A"] }, { ...original, columnCount: 0 }]) {
      expect(() => runOperation(invalid, { kind: "count", conditionColumn: 0, equals: "A" })).toThrow(Error);
    }
  });
});
