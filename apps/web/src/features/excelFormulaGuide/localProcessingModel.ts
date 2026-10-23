/** Values supported by the local-only plain-table workflow. Dates are stable text. */
export type PlainCell = string | number | boolean | null | { date: string };

export interface DataSheet {
  name: string;
  rows: PlainCell[][];
  warnings: string[];
  blockedReason?: string;
}

export interface LocalWorkbook {
  sourceName: string;
  sheets: DataSheet[];
}

export interface TableData {
  headers: PlainCell[] | null;
  rows: PlainCell[][];
  /** Original one-based Excel row numbers, retained through every operation. */
  rowNumbers: number[];
  columnCount: number;
}

export type OperationOptions =
  | { kind: "clean"; columns: number[]; removeBlankRows: boolean }
  | { kind: "dedupe"; columns: number[] }
  | { kind: "sum"; conditionColumn: number; equals: string; valueColumn: number }
  | { kind: "count"; conditionColumn: number; equals: string };

export interface RowIssue {
  row: number;
  /** One-based Excel column number. */
  column: number;
  message: string;
}

export interface OperationSummary {
  inputRows: number;
  outputRows: number;
  changedCells: number;
  removedRows: number;
  matchedRows: number;
  usedNumericRows: number;
  blankNumericRows: number;
}

export interface OperationResult extends TableData {
  kind: OperationOptions["kind"];
  summary: OperationSummary;
  issues: RowIssue[];
  /** Absent when a matching value cannot be safely included in a sum. */
  aggregate?: {
    value: string;
    exportCell: PlainCell;
    notice?: string;
  };
}

export const MAX_LOCAL_ROWS = 5_000;
export const MAX_LOCAL_COLUMNS = 50;
export const MAX_LOCAL_CELLS = 100_000;
