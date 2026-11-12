import { SSF } from "xlsx";
import type { TrialValue } from "./formulaTrial";

/** 沿用练习元数据的显示格式；只改变显示，不把日期或百分比结果反写为字符串参与计算。 */
export function formatTrialValue(value: TrialValue, numberFormat?: string): string {
  if (typeof value === "number" && numberFormat) return SSF.format(numberFormat, value);
  if (typeof value === "boolean") return value ? "TRUE" : "FALSE";
  return value === null ? "空白" : String(value);
}
