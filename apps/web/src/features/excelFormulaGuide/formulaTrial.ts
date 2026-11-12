import type { PracticeSheet } from "./model";

export type TrialValue = string | number | boolean | null;
export interface TrialSheet { name: string; rows: TrialValue[][]; dateColumns: number[] }
export interface TrialRequest { formula: string; sheetName: string; targetCell: string; sheets: TrialSheet[] }
export interface TrialResult { values: TrialValue[][] }
export const TRIAL_LIMITS = { formulaChars: 4096, valueChars: 2048, sheets: 10, rows: 500, columns: 50, cells: 10000, rangeCells: 5000, timeoutMs: 5000 } as const;
export const TRIAL_MESSAGES = {
  INVALID: "公式无法识别。请保留开头的等号，检查括号、引用和英文分隔符。",
  UNSUPPORTED: "本次写法或函数暂不支持。请使用本页教程中的函数和有界单元格范围。",
  LIMIT: "公式或范围超过本页试算上限，请缩小后重试。",
  CYCLE: "公式引用了自己的结果格，无法试算。请修改单元格引用。",
  SPILL: "展开结果会覆盖已有数据或超出试算区域，请换到连续空白区域。",
  DATE: "日期无效，请输入 1900 至 9999 年内有效的年、月、日。",
  TIMEOUT: "试算超过 5 秒，已终止。请缩小范围或简化公式后重试。",
  CANCELLED: "已停止本次试算。",
  WORKER: "试算模块未能加载，请刷新页面后重试。",
  "#DIV/0!": "#DIV/0!：分母为零，或没有可参与平均的数值。",
  "#N/A": "#N/A：没有找到匹配值。",
  "#VALUE!": "#VALUE!：参数类型或范围形状不正确。",
  "#REF!": "#REF!：单元格或工作表引用无效。",
  "#NAME?": "#NAME?：函数或名称无法识别。",
  "#NUM!": "#NUM!：数值超出函数允许的范围。",
  "#CALC!": "#CALC!：没有可返回的结果，请检查筛选条件。",
  "#NULL!": "#NULL!：引用范围没有交集。",
} as const;
export type TrialFailure = keyof typeof TRIAL_MESSAGES;
export type TrialResponse = { ok: true; result: TrialResult } | { ok: false; code: TrialFailure };
export class FormulaTrialError extends Error {
  /** 错误只携带固定代码，不把公式、单元格内容或底层异常输出到日志。 */
  constructor(public readonly code: TrialFailure) { super(TRIAL_MESSAGES[code]); }
}
export function isTrialValue(value: unknown): value is TrialValue {
  return value === null || typeof value === "boolean" || typeof value === "string" && value.length <= TRIAL_LIMITS.valueChars
    || typeof value === "number" && Number.isFinite(value);
}
/** Worker 消息以 unknown 进入，先验证必要字段及字面值类型，再交给计算层做范围/语义检查。 */
export function isTrialRequest(value: unknown): value is TrialRequest {
  if (!value || typeof value !== "object" || !("formula" in value) || typeof value.formula !== "string"
    || !("sheetName" in value) || typeof value.sheetName !== "string" || !("targetCell" in value) || typeof value.targetCell !== "string"
    || !("sheets" in value) || !Array.isArray(value.sheets)) return false;
  return value.sheets.every((sheet: unknown) => Boolean(sheet) && typeof sheet === "object" && sheet !== null
    && "name" in sheet && typeof sheet.name === "string" && "rows" in sheet && Array.isArray(sheet.rows)
    && sheet.rows.every((row: unknown) => Array.isArray(row) && row.every(isTrialValue))
    && "dateColumns" in sheet && Array.isArray(sheet.dateColumns) && sheet.dateColumns.every((column: unknown) => typeof column === "number"));
}
/** 将原固定示例复制为本题的独立输入；不读取文件、不沿用计算结果或持久化用户改动。 */
export function createTrialSheets(sheets: PracticeSheet[]): TrialSheet[] {
  return sheets.map((sheet) => ({ name: sheet.name, dateColumns: [...(sheet.dateColumns ?? [])],
    rows: [[...sheet.columns], ...sheet.rows.map((row) => [...row])] }));
}
/** 校验 Worker 返回的实际矩阵，拒绝异常对象、非有限数值和超大结果。 */
export function isTrialResult(value: unknown): value is TrialResult {
  if (!value || typeof value !== "object" || !("values" in value) || !Array.isArray(value.values) || !value.values.length) return false;
  const rows: unknown[] = value.values;
  const width = Array.isArray(rows[0]) ? rows[0].length : 0;
  return rows.length <= TRIAL_LIMITS.rows && rows.every((row) => Array.isArray(row) && row.length === width && row.length > 0
    && row.length <= TRIAL_LIMITS.columns && row.every(isTrialValue))
    && rows.reduce<number>((count, row) => count + (Array.isArray(row) ? row.length : 0), 0) <= TRIAL_LIMITS.rangeCells;
}
