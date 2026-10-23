import type { LocalWorkbook, OperationResult } from "./localProcessingModel";

export type WorkbookRequest =
  | { kind: "read"; buffer: ArrayBuffer; sourceName: string }
  | { kind: "write"; result: OperationResult; sheetName: string };

export type WorkbookResponse =
  | { ok: true; kind: "read"; workbook: LocalWorkbook }
  | { ok: true; kind: "write"; buffer: ArrayBuffer }
  | { ok: false; message: string };
