import type { LocalWorkbook, OperationResult } from "./localProcessingModel";
import type { WorkbookRequest, WorkbookResponse } from "./localWorkbookProtocol";

const MAX_FILE_BYTES = 5 * 1024 * 1024;
const WORKER_TIMEOUT_MS = 20_000;
const CANCEL_MESSAGE = "已取消本次文件处理。";
const TIMEOUT_MESSAGE = "处理超过 20 秒，已停止。请缩小工作表后重试。";

function isWorkbook(value: unknown): value is LocalWorkbook {
  if (!value || typeof value !== "object") return false;
  const workbook = value as Partial<LocalWorkbook>;
  return typeof workbook.sourceName === "string" && Array.isArray(workbook.sheets)
    && workbook.sheets.every((sheet) => sheet && typeof sheet.name === "string"
      && Array.isArray(sheet.rows) && sheet.rows.every(Array.isArray)
      && Array.isArray(sheet.warnings) && sheet.warnings.every((warning) => typeof warning === "string"));
}

export function createWorkbookClient() {
  let activeCancel: (() => void) | undefined;
  let generation = 0;
  let disposed = false;

  function cancel(): void {
    generation += 1;
    activeCancel?.();
    activeCancel = undefined;
  }

  function readFileBuffer(file: File): Promise<ArrayBuffer> {
    return new Promise((resolve, reject) => {
      let settled = false;
      const finish = (callback: () => void): void => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        if (activeCancel === cancelRead) activeCancel = undefined;
        callback();
      };
      const timer = setTimeout(() => finish(() => reject(new Error(TIMEOUT_MESSAGE))), WORKER_TIMEOUT_MS);
      const cancelRead = () => finish(() => reject(new Error(CANCEL_MESSAGE)));
      activeCancel = cancelRead;
      // The underlying File read cannot be aborted, but cancellation settles the
      // owning request immediately and late bytes can never start a worker.
      Promise.resolve().then(() => file.arrayBuffer()).then(
        (buffer) => finish(() => resolve(buffer)),
        () => finish(() => reject(new Error("读取所选文件失败，请重新选择后重试。"))),
      );
    });
  }

  function run(request: WorkbookRequest, transfer: Transferable[] = [], timeoutMs = WORKER_TIMEOUT_MS): Promise<WorkbookResponse> {
    if (disposed) return Promise.reject(new Error("当前页面已关闭。"));
    cancel();
    return new Promise((resolve, reject) => {
      let worker: Worker;
      try {
        worker = new Worker(new URL("./localWorkbook.worker.ts", import.meta.url), { type: "module" });
      } catch {
        reject(new Error("文件处理模块加载失败，请刷新页面后重试。"));
        return;
      }
      let settled = false;
      const finish = (callback: () => void): void => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        worker.onmessage = null;
        worker.onerror = null;
        worker.onmessageerror = null;
        worker.terminate();
        if (activeCancel === cancelWorker) activeCancel = undefined;
        callback();
      };
      const timer = setTimeout(() => finish(() => reject(new Error(TIMEOUT_MESSAGE))), timeoutMs);
      const cancelWorker = () => finish(() => reject(new Error(CANCEL_MESSAGE)));
      activeCancel = cancelWorker;
      worker.onmessage = (event: MessageEvent<unknown>) => {
        const response = event.data as Partial<WorkbookResponse> | null | undefined;
        const invalidMessage = request.kind === "read" ? "文件读取结果无效，请重试。" : "文件导出结果无效，请重试。";
        if (response && response.ok === false && "message" in response
          && typeof response.message === "string" && response.message.trim()) {
          finish(() => reject(new Error(response.message)));
        } else if (response && response.ok === true && response.kind === request.kind
          && ((response.kind === "read" && "workbook" in response && isWorkbook(response.workbook))
            || (response.kind === "write" && "buffer" in response && response.buffer instanceof ArrayBuffer))) {
          finish(() => resolve(response as WorkbookResponse));
        } else {
          finish(() => reject(new Error(invalidMessage)));
        }
      };
      worker.onerror = () => finish(() => reject(new Error("文件处理模块加载失败，请刷新页面后重试。")));
      worker.onmessageerror = () => finish(() => reject(new Error("文件处理结果无法读取，请重试。")));
      try {
        worker.postMessage(request, transfer);
      } catch {
        finish(() => reject(new Error("无法启动文件处理，请检查文件后重试。")));
      }
    });
  }

  async function read(file: File): Promise<LocalWorkbook> {
    cancel();
    const ownGeneration = generation;
    if (disposed) throw new Error("当前页面已关闭。");
    if (!/\.xlsx$/i.test(file.name)) throw new Error("目前只支持 .xlsx 文件，请先另存为此格式。");
    if (file.size === 0) throw new Error("文件为空，请重新选择。");
    if (file.size > MAX_FILE_BYTES) throw new Error("文件超过 5 MB，请缩小后重试。");
    const deadline = Date.now() + WORKER_TIMEOUT_MS;
    const buffer = await readFileBuffer(file);
    if (ownGeneration !== generation || disposed) throw new Error(CANCEL_MESSAGE);
    const remainingMs = deadline - Date.now();
    if (remainingMs <= 0) throw new Error(TIMEOUT_MESSAGE);
    const response = await run({ kind: "read", buffer, sourceName: file.name }, [buffer], remainingMs);
    if (!response.ok || response.kind !== "read") throw new Error("文件读取结果无效，请重试。");
    return response.workbook;
  }

  async function write(result: OperationResult, sheetName: string): Promise<ArrayBuffer> {
    const response = await run({ kind: "write", result, sheetName });
    if (!response.ok || response.kind !== "write") throw new Error("文件导出结果无效，请重试。");
    return response.buffer;
  }

  return { read, write, cancel, dispose: () => { disposed = true; cancel(); } };
}
