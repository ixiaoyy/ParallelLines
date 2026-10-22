import { generatePattern } from "./algorithm";
import { ARTKAL_S_COLORS } from "./palette";

// Worker 边界按未知输入校验；错误只回传状态，由主线程使用已确认的页面提示。
self.onmessage = (event: MessageEvent<unknown>) => {
  const payload = event.data;
  let id = -1;
  try {
    if (typeof payload !== "object" || payload === null || !("id" in payload)) {
      throw new Error("invalid_bead_worker_request");
    }
    if (typeof payload.id !== "number" || !Number.isSafeInteger(payload.id)) {
      throw new Error("invalid_bead_worker_request_id");
    }
    id = payload.id;
    if (
      !("width" in payload) || typeof payload.width !== "number"
      || !("height" in payload) || typeof payload.height !== "number"
      || !("maxColors" in payload) || typeof payload.maxColors !== "number"
      || !("data" in payload) || !(payload.data instanceof Uint8ClampedArray)
    ) throw new Error("invalid_bead_worker_payload");

    const pattern = generatePattern(payload.width, payload.height, payload.data, payload.maxColors, ARTKAL_S_COLORS);
    self.postMessage({ id, pattern });
  } catch {
    self.postMessage({ id, error: true });
  }
};
