import {
  MAX_LOCAL_CELLS,
  MAX_LOCAL_COLUMNS,
  MAX_LOCAL_ROWS,
  type DataSheet,
  type OperationOptions,
  type OperationResult,
  type PlainCell,
  type TableData,
} from "./localProcessingModel";

/** Display and condition comparison are literal; dates never become numbers. */
export function cellText(cell: PlainCell): string {
  if (cell === null) return "";
  if (typeof cell === "boolean") return cell ? "TRUE" : "FALSE";
  if (typeof cell === "object") return cell.date;
  return String(cell);
}

function cloneCell(cell: PlainCell): PlainCell {
  return cell !== null && typeof cell === "object" ? { date: cell.date } : cell;
}

function cloneRow(row: PlainCell[]): PlainCell[] {
  return row.map(cloneCell);
}

function isBlank(cell: PlainCell): boolean {
  return cell === null || (typeof cell === "string" && cell.trim() === "");
}

function validateSize(rowCount: number, columnCount: number): void {
  if (rowCount > MAX_LOCAL_ROWS || columnCount > MAX_LOCAL_COLUMNS
    || rowCount * columnCount > MAX_LOCAL_CELLS) {
    throw new Error("表格超过本工具的处理范围：最多 5000 行、50 列和 100000 个单元格。");
  }
}

/** Select a header in original Excel coordinates without mutating the source. */
export function buildTable(sheet: DataSheet, headerRow: number): TableData {
  if (sheet.blockedReason) throw new Error(sheet.blockedReason);
  if (!Number.isInteger(headerRow) || headerRow < 0 || headerRow > sheet.rows.length) {
    throw new Error("请选择有效的表头行，或选择“没有表头”。");
  }
  const columnCount = sheet.rows.reduce((max, row) => Math.max(max, row.length), 0);
  if (!columnCount || !sheet.rows.length) throw new Error("工作表没有可处理的数据。");
  validateSize(sheet.rows.length, columnCount);
  const padRow = (row: PlainCell[]): PlainCell[] =>
    Array.from({ length: columnCount }, (_, index) => cloneCell(row[index] ?? null));
  const headers = headerRow === 0 ? null : padRow(sheet.rows[headerRow - 1]!);
  if (headers && headers.every(isBlank)) {
    throw new Error("选中的表头行全部为空，请重新选择表头行或选择“没有表头”。");
  }
  return {
    headers,
    rows: sheet.rows.slice(headerRow).map(padRow),
    rowNumbers: sheet.rows.slice(headerRow).map((_, index) => headerRow + index + 1),
    columnCount,
  };
}

function validateTable(table: TableData): void {
  if (!Number.isInteger(table.columnCount) || table.columnCount < 1) {
    throw new Error("表格没有可处理的列。");
  }
  validateSize(table.rows.length, table.columnCount);
  if (table.headers && table.headers.length !== table.columnCount) {
    throw new Error("表头列数与数据不一致，请重新选择工作表。");
  }
  if (table.rows.length !== table.rowNumbers.length
    || table.rowNumbers.some((row) => !Number.isInteger(row) || row < 1)
    || table.rows.some((row) => row.length !== table.columnCount)) {
    throw new Error("表格行列信息不完整，请重新选择工作表。");
  }
}

function validateColumn(table: TableData, column: number): void {
  if (!Number.isInteger(column) || column < 0 || column >= table.columnCount) {
    throw new Error("请选择有效的处理列。");
  }
}

function selectedColumns(table: TableData, columns: number[]): number[] {
  if (!columns.length) throw new Error("请至少选择一列再处理。");
  columns.forEach((column) => validateColumn(table, column));
  return [...new Set(columns)];
}

function initialResult(table: TableData, kind: OperationOptions["kind"]): OperationResult {
  return {
    kind,
    headers: table.headers?.map(cloneCell) ?? null,
    rows: [],
    rowNumbers: [],
    columnCount: table.columnCount,
    summary: {
      inputRows: table.rows.length,
      outputRows: 0,
      changedCells: 0,
      removedRows: 0,
      matchedRows: 0,
      usedNumericRows: 0,
      blankNumericRows: 0,
    },
    issues: [],
  };
}

function validatePlainNumbers(table: TableData): void {
  table.rows.forEach((row, index) => {
    row.forEach((cell, column) => {
      if (typeof cell === "number" && (!Number.isFinite(cell)
        || (Number.isInteger(cell) && Math.abs(cell) >= 1e15))) {
        throw new Error(`原表第 ${table.rowNumbers[index]} 行、第 ${column + 1} 列含不支持的数字；长编号请先保存为文本。`);
      }
    });
  });
}

/** Typed keys avoid conflating 001, 1, false, blank, and date-looking text. */
function typedKey(cell: PlainCell): readonly [string, string | number | boolean | null] {
  if (cell === null) return ["blank", null];
  if (typeof cell === "object") return ["date", cell.date];
  return [typeof cell, cell];
}

interface Decimal {
  coefficient: bigint;
  scale: number;
}

type DecimalParse = { kind: "blank" } | { kind: "value"; decimal: Decimal } | { kind: "error"; message: string };

/** Expands only internally supplied finite JS numbers, never user expressions. */
function expandNumber(value: number): string {
  const text = String(value);
  if (!/[eE]/.test(text)) return text;
  const [mantissa = "", exponentText = "0"] = text.toLowerCase().split("e");
  const negative = mantissa.startsWith("-");
  const unsigned = negative ? mantissa.slice(1) : mantissa;
  const [integer = "0", fraction = ""] = unsigned.split(".");
  const digits = integer + fraction;
  const decimalPosition = integer.length + Number(exponentText);
  const expanded = decimalPosition <= 0
    ? `0.${"0".repeat(-decimalPosition)}${digits}`
    : decimalPosition >= digits.length
      ? digits + "0".repeat(decimalPosition - digits.length)
      : `${digits.slice(0, decimalPosition)}.${digits.slice(decimalPosition)}`;
  return negative ? `-${expanded}` : expanded;
}

function parsePlainDecimal(text: string): DecimalParse {
  if (!/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$/.test(text)) {
    return { kind: "error", message: "不是普通十进制数；请去掉千分位逗号、货币/百分比符号和科学计数写法。" };
  }
  const negative = text.startsWith("-");
  const unsigned = /^[+-]/.test(text) ? text.slice(1) : text;
  const [rawInteger = "", fraction = ""] = unsigned.split(".");
  const integer = rawInteger.replace(/^0+/, "") || "0";
  if (fraction.length > 12) {
    return { kind: "error", message: "小数部分超过 12 位，请先明确需要保留的精度。" };
  }
  if (integer.length + fraction.length > 30) {
    return { kind: "error", message: "数字超过 30 位处理范围，请缩短数值或保留为编号文本。" };
  }
  const coefficient = BigInt(integer + fraction) * (negative ? -1n : 1n);
  return { kind: "value", decimal: { coefficient, scale: fraction.length } };
}

function parseDecimal(cell: PlainCell): DecimalParse {
  if (isBlank(cell)) return { kind: "blank" };
  if (typeof cell === "boolean" || typeof cell === "object") {
    return { kind: "error", message: "日期和布尔值不能作为金额汇总。" };
  }
  if (typeof cell === "number") {
    if (!Number.isFinite(cell)) return { kind: "error", message: "数字不是有限数值，不能参与汇总。" };
    if (Number.isInteger(cell) && Math.abs(cell) >= 1e15) {
      return { kind: "error", message: "数字形式的整数超过 15 位，无法保证原始精度；请先在源文件中以文本保存。" };
    }
    return parsePlainDecimal(expandNumber(cell));
  }
  // isBlank has handled null, but keep the narrowing explicit for the public type.
  if (cell === null) return { kind: "blank" };
  return parsePlainDecimal(cell.trim());
}

function addDecimal(left: Decimal, right: Decimal): Decimal {
  const scale = Math.max(left.scale, right.scale);
  return {
    coefficient: left.coefficient * 10n ** BigInt(scale - left.scale)
      + right.coefficient * 10n ** BigInt(scale - right.scale),
    scale,
  };
}

function decimalText(decimal: Decimal): string {
  if (decimal.coefficient === 0n) return "0";
  const negative = decimal.coefficient < 0n;
  const digits = (negative ? -decimal.coefficient : decimal.coefficient).toString().padStart(decimal.scale + 1, "0");
  const text = decimal.scale === 0 ? digits
    : `${digits.slice(0, -decimal.scale)}.${digits.slice(-decimal.scale)}`.replace(/0+$/, "").replace(/\.$/, "");
  return negative ? `-${text}` : text;
}

function significantDigits(value: string): number {
  return value.replace(/[-.]/g, "").replace(/^0+/, "").length || 1;
}

function aggregateValue(value: string): NonNullable<OperationResult["aggregate"]> {
  const number = Number(value);
  const roundTrip = Number.isFinite(number) ? parsePlainDecimal(expandNumber(number)) : undefined;
  if (significantDigits(value) <= 15 && roundTrip?.kind === "value"
    && decimalText(roundTrip.decimal) === value) {
    return { value, exportCell: number };
  }
  return {
    value,
    exportCell: value,
    notice: "合计超出 Excel 可可靠表达的 15 位有效数字，已按文本导出以保留精度。",
  };
}

/** Every invocation starts from the provided original table; no mutation or eval. */
export function runOperation(table: TableData, options: OperationOptions): OperationResult {
  validateTable(table);
  const result = initialResult(table, options.kind);
  if (options.kind === "clean") {
    const columns = selectedColumns(table, options.columns);
    validatePlainNumbers(table);
    table.rows.forEach((original, index) => {
      const row = cloneRow(original);
      let changed = 0;
      columns.forEach((column) => {
        const value = row[column];
        if (typeof value === "string") {
          row[column] = value.trim();
          if (row[column] !== value) changed += 1;
        }
      });
      if (options.removeBlankRows && row.every(isBlank)) {
        result.summary.removedRows += 1;
        return;
      }
      result.summary.changedCells += changed;
      result.rows.push(row);
      result.rowNumbers.push(table.rowNumbers[index]!);
    });
  } else if (options.kind === "dedupe") {
    const columns = selectedColumns(table, options.columns);
    validatePlainNumbers(table);
    const seen = new Set<string>();
    table.rows.forEach((row, index) => {
      const key = JSON.stringify(columns.map((column) => typedKey(row[column]!)));
      if (seen.has(key)) {
        result.summary.removedRows += 1;
        return;
      }
      seen.add(key);
      result.rows.push(cloneRow(row));
      result.rowNumbers.push(table.rowNumbers[index]!);
    });
  } else if (options.kind === "sum" || options.kind === "count") {
    validateColumn(table, options.conditionColumn);
    if (typeof options.equals !== "string") throw new Error("请输入要精确匹配的条件值。");
    if (options.kind === "sum") validateColumn(table, options.valueColumn);
    let sum: Decimal = { coefficient: 0n, scale: 0 };
    table.rows.forEach((row, index) => {
      if (cellText(row[options.conditionColumn]!) !== options.equals) return;
      result.rows.push(cloneRow(row));
      result.rowNumbers.push(table.rowNumbers[index]!);
      result.summary.matchedRows += 1;
      if (options.kind !== "sum") return;
      const parsed = parseDecimal(row[options.valueColumn]!);
      if (parsed.kind === "blank") result.summary.blankNumericRows += 1;
      else if (parsed.kind === "error") {
        result.issues.push({ row: table.rowNumbers[index]!, column: options.valueColumn + 1, message: parsed.message });
      } else {
        result.summary.usedNumericRows += 1;
        sum = addDecimal(sum, parsed.decimal);
      }
    });
    if (options.kind === "count") {
      result.aggregate = { value: String(result.summary.matchedRows), exportCell: result.summary.matchedRows };
    } else if (result.issues.length === 0) {
      const value = decimalText(sum);
      if (significantDigits(value) > 30) {
        result.issues.push({
          row: result.rowNumbers.at(-1) ?? 1,
          column: options.valueColumn + 1,
          message: "合计结果超过 30 位数字范围，请缩小处理范围；这不是单独一行的错误。",
        });
      } else result.aggregate = aggregateValue(value);
    }
  } else {
    throw new Error("暂不支持这个处理操作。");
  }
  result.summary.outputRows = result.rows.length;
  return result;
}
