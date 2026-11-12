import type { OperationOptions } from "./localProcessingModel";

export type OnlineOperationId = "compare" | OperationOptions["kind"];
export interface OnlineOperation {
  id: OnlineOperationId;
  title: string;
  description: string;
  keywords: string[];
}

// 只登记现有本地能力，单条件工具不冒充多条件公式或完整在线 Excel。
export const onlineOperations: OnlineOperation[] = [
  { id: "compare", title: "两列名单查重比对", description: "粘贴两列名单，找两边都有、仅一边有的记录。", keywords: ["查重", "重复", "对比", "比对", "核对提交名单", "漏交", "人员名单", "交集", "差集", "粘贴名单"] },
  { id: "clean", title: "清理空格与空行", description: "选择本地 Excel，清理文字前后空格及全空行。", keywords: ["清洗", "数据清理", "空白", "多余空格", "删除空行", "TRIM", "xlsx"] },
  { id: "dedupe", title: "按列去重", description: "选择要比较的列，生成去重后的新表，不覆盖原文件。", keywords: ["去重", "不重复", "唯一值", "UNIQUE", "删除重复行", "重复记录", "xlsx"] },
  { id: "sum", title: "按条件汇总金额", description: "选择一个条件和金额列，计算匹配记录的合计。", keywords: ["求和", "合计", "金额汇总", "按人汇总", "按人员汇总", "总金额", "SUMIF", "单条件求和", "xlsx"] },
  { id: "count", title: "按条件统计条数", description: "按一个条件数记录条数，不把记录数当作人数。", keywords: ["计数", "记录数量", "数记录", "COUNTIF", "单条件计数", "xlsx"] },
];
