import { FormulaTrialError, TRIAL_LIMITS, TRIAL_MESSAGES, isTrialResult, type TrialFailure, type TrialRequest, type TrialResult } from "./formulaTrial";

/** 本页试算专用客户端；每次独占 Worker，取消、超时和结束均 terminate，不影响文件处理能力。 */
export function createFormulaTrialClient() {
  let activeCancel: (() => void) | undefined;
  let disposed = false;

  function cancel(): void { activeCancel?.(); activeCancel = undefined; }

  /** 只接收有界示例输入，返回真实计算矩阵；模块失败、非法消息和超时均为显式失败。 */
  function calculate(request: TrialRequest): Promise<TrialResult> {
    cancel();
    if (disposed) return Promise.reject(new FormulaTrialError("CANCELLED"));
    return new Promise((resolve, reject) => {
      let worker: Worker;
      try { worker = new Worker(new URL("./formulaTrial.worker.ts", import.meta.url), { type: "module" }); }
      catch { reject(new FormulaTrialError("WORKER")); return; }
      let settled = false;
      const finish = (callback: () => void) => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        worker.onmessage = worker.onerror = worker.onmessageerror = null;
        if (activeCancel === cancelThis) activeCancel = undefined;
        try { worker.terminate(); }
        catch { reject(new FormulaTrialError("WORKER")); return; }
        callback();
      };
      const timer = setTimeout(() => finish(() => reject(new FormulaTrialError("TIMEOUT"))), TRIAL_LIMITS.timeoutMs);
      const cancelThis = () => finish(() => reject(new FormulaTrialError("CANCELLED")));
      activeCancel = cancelThis;
      worker.onmessage = (event: MessageEvent<unknown>) => {
        const response = event.data;
        if (response && typeof response === "object" && "ok" in response && response.ok === true && "result" in response && isTrialResult(response.result)) {
          const result = response.result;
          finish(() => resolve(result));
        } else if (response && typeof response === "object" && "ok" in response && response.ok === false && "code" in response
          && typeof response.code === "string" && Object.hasOwn(TRIAL_MESSAGES, response.code)) {
          const code = response.code as TrialFailure;
          finish(() => reject(new FormulaTrialError(code)));
        } else finish(() => reject(new FormulaTrialError("INVALID")));
      };
      worker.onerror = (event) => { event.preventDefault(); finish(() => reject(new FormulaTrialError("WORKER"))); };
      worker.onmessageerror = () => finish(() => reject(new FormulaTrialError("INVALID")));
      try { worker.postMessage(request); }
      catch { finish(() => reject(new FormulaTrialError("INVALID"))); }
    });
  }
  return { calculate, cancel, dispose: () => { disposed = true; cancel(); } };
}
