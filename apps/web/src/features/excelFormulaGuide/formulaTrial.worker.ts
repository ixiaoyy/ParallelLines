import { calculateFormulaTrial } from "./formulaTrialEngine";
import { FormulaTrialError, type TrialResponse } from "./formulaTrial";

// 试算与文件清理完全分开；仅响应当前独立 Worker 的一次输入，不读文件、不联网、不保存记录。
self.onmessage = (event: MessageEvent<unknown>) => {
  let response: TrialResponse;
  try { response = { ok: true, result: calculateFormulaTrial(event.data) }; }
  catch (error) { response = { ok: false, code: error instanceof FormulaTrialError ? error.code : "INVALID" }; }
  self.postMessage(response);
};
