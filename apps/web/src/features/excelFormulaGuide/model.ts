/** 按用户想得到的结果组织教程，分组只负责选课，不改变公式或练习数据。 */
export interface FormulaTaskGroup {
  id: string;
  title: string;
  description: string;
  lessonIds: string[];
}

/** 一篇零基础公式教程，示例位置与配套练习工作簿保持一致。 */
export interface FormulaLesson {
  id: string;
  title: string;
  category: string;
  functions: string[];
  keywords: string[];
  summary: string;
  selectionTip?: string;
  relatedLesson?: { id: string; label: string };
  scenario: string;
  version: string;
  minExcelVersion?: number;
  exampleSheets?: string[];
  expectedValues?: (string | number)[];
  sheetName: string;
  targetCell: string;
  formula: string;
  expected: string;
  steps: { title: string; detail: string }[];
  parts: { fragment: string; meaning: string }[];
  checks: string[];
  pitfalls: { problem: string; solution: string }[];
  extension: string;
  sources: { title: string; url: string }[];
}

/** 表格演示只展示固定练习数据，不读取或保存用户文件。 */
export interface PracticeSheet {
  name: string;
  description: string;
  columns: string[];
  rows: (string | number)[][];
  dateColumns?: number[];
}

export const PRACTICE_WORKBOOK_URL = "/tools/excel-formulas/excel-formula-practice.xlsx";
