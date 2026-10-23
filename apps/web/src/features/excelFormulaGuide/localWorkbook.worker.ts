import { readLocalWorkbook, writeOperationWorkbook } from "./localWorkbook";
import type { WorkbookRequest, WorkbookResponse } from "./localWorkbookProtocol";

// This dedicated worker has no network or persistence calls. Only file bytes and
// bounded plain-table results cross the message boundary with its owning page.
self.addEventListener("message", (event: MessageEvent<WorkbookRequest>) => {
  try {
    const request = event.data;
    if (request.kind === "read") {
      const response: WorkbookResponse = {
        ok: true, kind: "read", workbook: readLocalWorkbook(request.buffer, request.sourceName),
      };
      self.postMessage(response);
    } else {
      const buffer = writeOperationWorkbook(request.result, request.sheetName);
      const response: WorkbookResponse = { ok: true, kind: "write", buffer };
      self.postMessage(response, { transfer: [buffer] });
    }
  } catch (error) {
    const response: WorkbookResponse = {
      ok: false, message: error instanceof Error ? error.message : "文件处理失败，请检查文件后重试。",
    };
    self.postMessage(response);
  }
});
