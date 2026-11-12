import XLSX_CALC from "xlsx-calc";
import * as F from "@formulajs/formulajs";
import { SSF } from "xlsx";
import { FormulaTrialError, TRIAL_LIMITS, TRIAL_MESSAGES, isTrialValue, isTrialRequest, isTrialResult, type TrialRequest, type TrialResult, type TrialValue, type TrialFailure } from "./formulaTrial";

export const TRIAL_FUNCTIONS = ["AND", "AVERAGE", "AVERAGEIFS", "COUNT", "COUNTA", "COUNTBLANK", "COUNTIFS", "DATE", "DAY", "EDATE", "FILTER", "FIND", "IF", "IFERROR", "IFNA", "INDEX", "INT", "LARGE", "LEFT", "LEN", "MATCH", "MAX", "MID", "MIN", "MONTH", "NETWORKDAYS", "NOT", "OR", "RANK.EQ", "RIGHT", "ROUND", "ROUNDDOWN", "ROUNDUP", "SORT", "SUBSTITUTE", "SUBTOTAL", "SUM", "SUMIFS", "TEXT", "TEXTJOIN", "TRIM", "UNIQUE", "VLOOKUP", "XLOOKUP", "YEAR"] as const;
interface Cell { t?: string; v?: unknown; f?: string; w?: string }
type Sheet = Record<string, Cell>;
type Matrix = TrialValue[][];
interface RawExpression { calc(): unknown }
const excelError = (code: string) => new Error(code);
const EXCEL_ERROR_CODES = new Set(["#NULL!", "#DIV/0!", "#VALUE!", "#REF!", "#NAME?", "#NUM!", "#N/A", "#GETTING_DATA", "#CALC!"]);

/** raw 参数可能返回 Error 对象，也可能抛出；在同一错误边界处理，但不吞掉资源/能力守卫。 */
function rawValue(expression: RawExpression): unknown {
  const value = expression.calc();
  if (value instanceof Error) throw value;
  return value;
}
function isExcelCalculationError(error: unknown): error is Error {
  return error instanceof Error && !(error instanceof FormulaTrialError) && EXCEL_ERROR_CODES.has(error.message);
}

function matrix(value: unknown): Matrix {
  const rows = Array.isArray(value) ? value : [[value]];
  const result = rows.map((row) => Array.isArray(row) ? row : [row]);
  if (!result.length || !result[0]?.length || result.some((row) => row.length !== result[0]!.length
    || row.some((cell) => !isTrialValue(cell)))) throw excelError("#VALUE!");
  if (result.length * result[0]!.length > TRIAL_LIMITS.rangeCells) throw new FormulaTrialError("LIMIT");
  return result;
}

/** 用成熟 COUNTIFS 比较普通条件；仅修正该库会跳过的 Excel 文本通配符分支。 */
function matchesCriterion(value: TrialValue, criterion: unknown): boolean {
  if (typeof criterion === "string" && /[*?~]/.test(criterion)) {
    const not = criterion.startsWith("<>");
    const pattern = criterion.replace(/^(?:<>|=)/, "");
    if (/^[<>]/.test(pattern) || (pattern.match(/[*?]/g)?.length ?? 0) > 16) throw new FormulaTrialError("UNSUPPORTED");
    let body = "";
    const escape = (char: string) => char.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    for (let index = 0; index < pattern.length; index++) {
      const char = pattern[index]!;
      if (char === "~" && index + 1 < pattern.length) body += escape(pattern[++index]!);
      else body += char === "*" ? ".*" : char === "?" ? "." : escape(char);
    }
    const match = typeof value === "string" && new RegExp(`^${body}$`, "iu").test(value);
    return not ? !match : match;
  }
  return F.COUNTIFS([[value]], criterion ?? "") === 1;
}

/** IFS 仅适配同形状范围，数值聚合忽略文本；无匹配平均明确失败，不能变成成功的零。 */
function conditionalAggregate(kind: "sum" | "average" | "count", args: unknown[]): unknown {
  const start = kind === "count" ? 0 : 1;
  if (args.length < start + 2 || (args.length - start) % 2) throw excelError("#VALUE!");
  const base = matrix(args[0]);
  const pairs: { range: Matrix; criterion: unknown }[] = [];
  for (let index = start; index < args.length; index += 2) {
    const range = matrix(args[index]);
    if (range.length !== base.length || range[0]!.length !== base[0]!.length) throw excelError("#VALUE!");
    pairs.push({ range, criterion: args[index + 1] });
  }
  const values: TrialValue[] = [];
  base.forEach((row, r) => row.forEach((value, c) => {
    if (pairs.every((pair) => matchesCriterion(pair.range[r]![c]!, pair.criterion))) values.push(value);
  }));
  if (kind === "count") return values.length;
  const numbers = values.filter((value): value is number => typeof value === "number");
  return kind === "sum" ? F.SUM(numbers) : numbers.length ? F.AVERAGE(numbers) : excelError("#DIV/0!");
}

/** FILTER 返回紧凑的真实行/列矩阵，不填充到输入高度，也不从示例答案取值。 */
function filter(array: unknown, include: unknown, fallback?: unknown): unknown {
  const data = matrix(array), mask = matrix(include);
  const truth = (value: TrialValue) => {
    if (typeof value !== "boolean" && typeof value !== "number") throw excelError("#VALUE!");
    return Boolean(value);
  };
  let result: Matrix;
  if (mask.length === data.length && mask[0]!.length === 1) result = data.filter((_, index) => truth(mask[index]![0]!));
  else if (mask.length === 1 && mask[0]!.length === data[0]!.length) result = data.map((row) => row.filter((_, index) => truth(mask[0]![index]!)));
  else throw excelError("#VALUE!");
  return result.length && result[0]?.length ? result : fallback !== undefined ? matrix(fallback) : excelError("#CALC!");
}

/** SORT 保留二维行形状及稳定排序，数字按数值比较；当前不实现横向按列排序。 */
function sort(array: unknown, index: unknown = 1, order: unknown = 1, byColumn: unknown = false): unknown {
  const data = matrix(array);
  if (byColumn) throw new FormulaTrialError("UNSUPPORTED");
  if (typeof index !== "number" || !Number.isInteger(index) || index < 1 || index > data[0]!.length || order !== 1 && order !== -1) throw excelError("#VALUE!");
  const compare = (left: TrialValue, right: TrialValue) => {
    if (typeof left === "number" && typeof right === "number") return left - right;
    if (typeof left === "number") return -1;
    if (typeof right === "number") return 1;
    return String(left ?? "").localeCompare(String(right ?? ""), "zh-CN", { sensitivity: "base" });
  };
  return data.map((row, position) => ({ row, position })).sort((a, b) => Number(order) * compare(a.row[Number(index) - 1]!, b.row[Number(index) - 1]!) || a.position - b.position).map((item) => item.row);
}

/** UNIQUE 按完整行去重，保留第一次出现的行；其他 Excel 模式明确不支持而不猜结果。 */
function unique(array: unknown, byColumn: unknown = false, exactlyOnce: unknown = false): unknown {
  if (byColumn || exactlyOnce) throw new FormulaTrialError("UNSUPPORTED");
  const seen = new Set<string>();
  return matrix(array).filter((row) => {
    const key = JSON.stringify(row.map((value) => typeof value === "string" ? value.toLocaleLowerCase() : value));
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

/** XLOOKUP 只做精确匹配与缺失回退，保持文本/数值类型，支持查找列返回一行结果。 */
function xlookup(value: unknown, lookup: unknown, output: unknown, missing?: unknown, mode: unknown = 0, direction: unknown = 1): unknown {
  if (mode !== 0 || direction !== 1) throw new FormulaTrialError("UNSUPPORTED");
  const keys = matrix(lookup), rows = matrix(output);
  if (keys[0]!.length !== 1 || rows.length !== keys.length) throw excelError("#VALUE!");
  const found = keys.findIndex((row) => typeof value === "string" && typeof row[0] === "string"
    ? value.toLocaleLowerCase() === row[0].toLocaleLowerCase() : value === row[0]);
  return found < 0 ? missing === undefined ? excelError("#N/A") : missing : rows[found]!.length === 1 ? rows[found]![0] : [rows[found]!];
}

// 仅导入运行库 ESM 入口与所需函数；不加载 FormulaJS CLI，也不注册可联网或执行脚本的扩展。
F.utils.date.useSerial();
const functions: Record<string, unknown> = {};
for (const name of TRIAL_FUNCTIONS) {
  const fn: unknown = name === "RANK.EQ" ? F.RANK.EQ : F[name as keyof typeof F];
  if (typeof fn === "function") functions[name] = fn;
}
functions.TEXT = (value: unknown, format: unknown) => typeof value === "number" && typeof format === "string" ? SSF.format(format, value) : excelError("#VALUE!");
functions.COUNTIFS = (...args: unknown[]) => conditionalAggregate("count", args);
functions.SUMIFS = (...args: unknown[]) => conditionalAggregate("sum", args);
functions.AVERAGEIFS = (...args: unknown[]) => conditionalAggregate("average", args);
// FormulaJS 的本地 1900 epoch + ceil 会受历史时区影响；只适配日期表示，不改成熟函数的月末规则。
const dateResult = (operation: () => unknown): unknown => {
  F.utils.date.useDate();
  try {
    const result = operation();
    if (!(result instanceof Date)) return result;
    if (!Number.isFinite(result.getTime()) || result.getFullYear() < 1900 || result.getFullYear() > 9999) return excelError("#NUM!");
    return calendarSerial(result.getFullYear(), result.getMonth() + 1, result.getDate());
  } finally { F.utils.date.useSerial(); }
};
functions.DATE = (year: unknown, month: unknown, day: unknown) => dateResult(() => F.DATE(year, month, day));
functions.EDATE = (start: unknown, months: unknown) => start === 60 ? excelError("#NUM!") : dateResult(() => F.EDATE(start, months));
functions.DAY = (value: unknown) => typeof value === "number" ? SSF.parse_date_code(value)?.d ?? excelError("#NUM!") : F.DAY(value);
functions.MONTH = (value: unknown) => typeof value === "number" ? SSF.parse_date_code(value)?.m ?? excelError("#NUM!") : F.MONTH(value);
functions.YEAR = (value: unknown) => typeof value === "number" ? SSF.parse_date_code(value)?.y ?? excelError("#NUM!") : F.YEAR(value);
XLSX_CALC.import_functions(functions, { override: true });
XLSX_CALC.set_fx("FILTER", filter);
XLSX_CALC.set_fx("SORT", sort);
XLSX_CALC.set_fx("UNIQUE", unique);
XLSX_CALC.set_fx("XLOOKUP", xlookup);
// 仅供规范化后的布尔字面量使用；不加入用户函数许可列表，避免 parser 将类型折成 1/0。
XLSX_CALC.set_fx("PLBOOLTRUE", () => true);
XLSX_CALC.set_fx("PLBOOLFALSE", () => false);
XLSX_CALC.import_raw_functions({
  IFERROR: (value: RawExpression, fallback: RawExpression) => {
    let result: unknown;
    try { result = rawValue(value); } catch (error) {
      if (isExcelCalculationError(error)) return fallback.calc();
      throw error;
    }
    return typeof result === "number" && !Number.isFinite(result) ? fallback.calc() : result;
  },
  IFNA: (value: RawExpression, fallback: RawExpression) => {
    try { return rawValue(value); } catch (error) {
      if (isExcelCalculationError(error) && error.message === "#N/A") return fallback.calc();
      throw error;
    }
  },
  AND: (...values: RawExpression[]) => F.AND(...values.map((value) => value.calc())),
  OR: (...values: RawExpression[]) => F.OR(...values.map((value) => value.calc())),
});

function coordinate(value: string): { row: number; column: number } {
  const match = /^\$?([A-Z]+)\$?(\d+)$/i.exec(value);
  if (!match) throw new FormulaTrialError("INVALID");
  const column = [...match[1]!.toUpperCase()].reduce((total, char) => total * 26 + char.charCodeAt(0) - 64, 0);
  const row = Number(match[2]);
  if (row < 1 || row > TRIAL_LIMITS.rows || column > TRIAL_LIMITS.columns) throw new FormulaTrialError("LIMIT");
  return { row, column };
}
function address(row: number, column: number): string {
  let name = "";
  while (column > 0) { column--; name = String.fromCharCode(65 + column % 26) + name; column = Math.floor(column / 26); }
  return `${name}${row}`;
}
function serialDate(value: string): number {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) throw new FormulaTrialError("DATE");
  const date = new Date(`${value}T00:00:00.000Z`);
  if (!Number.isFinite(date.getTime()) || date.toISOString().slice(0, 10) !== value || date.getUTCFullYear() < 1900) throw new FormulaTrialError("DATE");
  return calendarSerial(date.getUTCFullYear(), date.getUTCMonth() + 1, date.getUTCDate());
}

/** 按 UTC 日历编码 Excel 1900 日期，避免时区/DST；保留 Excel 在 1900-03-01 之后的闰日偏移。 */
function calendarSerial(year: number, month: number, day: number): number {
  const utc = Date.UTC(year, month - 1, day);
  return (utc - Date.UTC(1899, 11, 31)) / 86400000 + (utc >= Date.UTC(1900, 2, 1) ? 1 : 0);
}

/** 输入许可检查只负责资源/来源边界和名称规范；实际公式解析与计算仍由成熟引擎执行。 */
function validate(request: TrialRequest): string {
  if (!request || typeof request.formula !== "string" || !request.formula.trim().startsWith("=") || request.formula.length > TRIAL_LIMITS.formulaChars) throw new FormulaTrialError("LIMIT");
  if (!Array.isArray(request.sheets) || !request.sheets.length || request.sheets.length > TRIAL_LIMITS.sheets) throw new FormulaTrialError("LIMIT");
  let cells = 0;
  const names = new Set<string>();
  for (const sheet of request.sheets) {
    if (!sheet || typeof sheet.name !== "string" || !sheet.name || sheet.name.length > 40 || names.has(sheet.name) || !Array.isArray(sheet.rows)
      || sheet.rows.length > TRIAL_LIMITS.rows || !Array.isArray(sheet.dateColumns) || sheet.dateColumns.some((column) => !Number.isInteger(column) || column < 0 || column >= TRIAL_LIMITS.columns)) throw new FormulaTrialError("LIMIT");
    names.add(sheet.name);
    for (const row of sheet.rows) {
      if (!Array.isArray(row) || row.length > TRIAL_LIMITS.columns || row.some((value) => !isTrialValue(value))) throw new FormulaTrialError("LIMIT");
      cells += row.length;
    }
  }
  if (cells > TRIAL_LIMITS.cells || !names.has(request.sheetName)) throw new FormulaTrialError("LIMIT");
  const target = coordinate(request.targetCell);
  let formula = request.formula.trim();
  // 双引号常量不作为函数、地址或外链检查对象；工作表名只允许引用本次输入中的已知名称。
  const maskStrings = (value: string) => value.replace(/"(?:[^"]|"")*"/g, (text) => " ".repeat(text.length));
  const masked = maskStrings(formula);
  if (/[\[\]`{}]/.test(masked) || /\b[A-Z]+\s*:\s*[A-Z]+\b/i.test(masked) || /\b\d+\s*:\s*\d+\b/.test(masked)) throw new FormulaTrialError("UNSUPPORTED");
  const refs = /(^|[^A-Z0-9_.])(?:(?:'((?:[^']|'')*)'|([A-Z_\u4e00-\u9fff][A-Z0-9_\u4e00-\u9fff]*))\s*!\s*)?(\$?[A-Z]{1,3}\$?\d+)(?:\s*:\s*(\$?[A-Z]{1,3}\$?\d+))?/gi;
  const replacements: { start: number; end: number; text: string }[] = [];
  let remainder = masked.replace(refs, (full, prefix: string, quoted: string | undefined, plain: string | undefined, first: string, last: string | undefined, index: number) => {
    const sheet = quoted !== undefined ? quoted.replace(/''/g, "'") : plain ?? request.sheetName;
    if (!names.has(sheet)) throw new FormulaTrialError("#REF!");
    const from = coordinate(first), to = coordinate(last ?? first);
    if (from.row > to.row || from.column > to.column || (to.row - from.row + 1) * (to.column - from.column + 1) > TRIAL_LIMITS.rangeCells) throw new FormulaTrialError("LIMIT");
    if (sheet === request.sheetName && target.row >= from.row && target.row <= to.row && target.column >= from.column && target.column <= to.column) throw new FormulaTrialError("CYCLE");
    replacements.push({ start: index + prefix.length, end: index + full.length,
      text: `${quoted !== undefined || plain !== undefined ? `'${sheet.replace(/'/g, "''")}'!` : ""}${first.toUpperCase()}${last ? `:${last.toUpperCase()}` : ""}` });
    return `${prefix}@`;
  });
  const allowed = new Set<string>(TRIAL_FUNCTIONS);
  remainder = remainder.replace(/\b([A-Z][A-Z0-9_.]*)\s*\(/gi, (_text, name: string) => {
    if (!allowed.has(name.toUpperCase())) throw new FormulaTrialError("UNSUPPORTED");
    return "(";
  }).replace(/\b(?:TRUE|FALSE)\b/gi, "@").replace(/(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?/gi, "@");
  if (/[^\s@=+\-*/^&<>()%,:]/.test(remainder) || /@\s*@/.test(remainder)) throw new FormulaTrialError("INVALID");
  for (const replacement of replacements.reverse()) formula = formula.slice(0, replacement.start) + replacement.text + formula.slice(replacement.end);
  return formula.split(/("(?:[^"]|"")*"|'(?:[^']|'')*')/g).map((part, index) => index % 2 ? part : part.replace(/\b([A-Z][A-Z0-9_.]*)(?=\s*\()/gi, (name) => name.toUpperCase())
    .replace(/\b(?:TRUE|FALSE)\b(?!\s*\()/gi, (value) => value.toUpperCase() === "TRUE" ? "PLBOOLTRUE()" : "PLBOOLFALSE()")).join("");
}

/** 仅从当前可编辑输入构造私有工作簿，捕获引擎最终矩阵并在写邻格前检查覆盖。 */
export function calculateFormulaTrial(input: unknown): TrialResult {
  if (!isTrialRequest(input)) throw new FormulaTrialError("INVALID");
  const request = input;
  const formula = validate(request);
  const sheets: Record<string, Sheet> = Object.create(null);
  for (const input of request.sheets) {
    const sheet: Sheet = Object.create(null);
    input.rows.forEach((row, r) => row.forEach((value, c) => {
      if (value === null || value === "") return;
      const parsed = r > 0 && input.dateColumns.includes(c) ? typeof value === "string" ? serialDate(value) : value : value;
      sheet[address(r + 1, c + 1)] = { t: typeof parsed === "number" ? "n" : typeof parsed === "boolean" ? "b" : "s", v: parsed };
    }));
    sheets[input.name] = sheet;
  }
  const sheet = sheets[request.sheetName]!;
  const origin = coordinate(request.targetCell);
  const target: Cell = { f: formula.slice(1) };
  let value: unknown;
  let spill: Matrix | undefined;
  Object.defineProperty(target, "v", { enumerable: true, configurable: true, get: () => value, set: (next: unknown) => {
    if (next instanceof Error) throw next;
    if (Array.isArray(next)) {
      const result = matrix(next);
      if (origin.row + result.length - 1 > TRIAL_LIMITS.rows || origin.column + result[0]!.length - 1 > TRIAL_LIMITS.columns) throw new FormulaTrialError("SPILL");
      result.forEach((row, r) => row.forEach((_cell, c) => {
        if (r === 0 && c === 0) return;
        const existing = sheet[address(origin.row + r, origin.column + c)]?.v;
        if (existing !== undefined && existing !== null && existing !== "") throw new FormulaTrialError("SPILL");
      }));
      spill = result.map((row) => [...row]);
    }
    value = next;
  } });
  sheet[request.targetCell.toUpperCase().replace(/\$/g, "")] = target;
  try {
    XLSX_CALC({ SheetNames: Object.keys(sheets), Sheets: sheets }, { continue_after_error: false, log_error: false });
  } catch (error) {
    if (error instanceof FormulaTrialError) throw error;
    if (error instanceof Error && Object.hasOwn(TRIAL_MESSAGES, error.message)) throw new FormulaTrialError(error.message as TrialFailure);
    throw new FormulaTrialError("INVALID");
  }
  if (target.t === "e") throw new FormulaTrialError(target.w && Object.hasOwn(TRIAL_MESSAGES, target.w) ? target.w as TrialFailure : "INVALID");
  const result = { values: spill ?? [[value]] };
  if (!isTrialResult(result)) throw new FormulaTrialError("INVALID");
  return result;
}
