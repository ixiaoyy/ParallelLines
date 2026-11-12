import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createFormulaTrialClient } from "./formulaTrialClient";
import { TRIAL_LIMITS, type TrialRequest } from "./formulaTrial";

class FakeWorker {
  static instances: FakeWorker[] = [];
  static failConstruction = false;
  static failPost = false;
  onmessage: ((event: MessageEvent<unknown>) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onmessageerror: ((event: Event) => void) | null = null;
  terminate = vi.fn();
  postMessage = vi.fn(() => { if (FakeWorker.failPost) throw new Error("private post detail"); });
  constructor(public readonly url: URL, public readonly options: WorkerOptions) {
    if (FakeWorker.failConstruction) throw new Error("private constructor detail");
    FakeWorker.instances.push(this);
  }
  send(data: unknown) { this.onmessage?.({ data } as MessageEvent<unknown>); }
}
const request: TrialRequest = { formula: "=1+2", sheetName: "练习", targetCell: "C2", sheets: [{ name: "练习", rows: [["", "", ""]], dateColumns: [] }] };
beforeEach(() => { FakeWorker.instances = []; FakeWorker.failConstruction = false; FakeWorker.failPost = false; vi.stubGlobal("Worker", FakeWorker); });
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); vi.useRealTimers(); });

describe("公式试算专用 Worker 生命周期", () => {
  it("只创建当前模块 Worker，成功后保留零/布尔/文本工号/空值并终止线程", async () => {
    const client = createFormulaTrialClient();
    const promise = client.calculate(request);
    const worker = FakeWorker.instances[0]!;
    expect(worker.url.pathname).toContain("formulaTrial.worker.ts");
    expect(worker.options).toEqual({ type: "module" });
    worker.send({ ok: true, result: { values: [[0, false, "001", null]] } });
    await expect(promise).resolves.toEqual({ values: [[0, false, "001", null]] });
    expect(worker.terminate).toHaveBeenCalledOnce();
    expect(worker.onmessage).toBeNull();
  });

  it.each([null, { ok: true, result: { values: [[NaN]] } }, { ok: true, result: { values: [[1, 2], [3]] } }, { ok: false, code: "toString" }])("拒绝不合法消息而不发布结果：%j", async (message) => {
    const client = createFormulaTrialClient();
    const promise = client.calculate(request);
    FakeWorker.instances[0]!.send(message);
    await expect(promise).rejects.toMatchObject({ code: "INVALID" });
    expect(FakeWorker.instances[0]!.terminate).toHaveBeenCalledOnce();
  });

  it("新试算立即取消旧试算，迟到消息不能覆盖新结果", async () => {
    const client = createFormulaTrialClient();
    const first = client.calculate(request);
    const old = FakeWorker.instances[0]!;
    const late = old.onmessage;
    const rejected = expect(first).rejects.toMatchObject({ code: "CANCELLED" });
    const second = client.calculate(request);
    await rejected;
    late?.({ data: { ok: true, result: { values: [[999]] } } } as MessageEvent<unknown>);
    FakeWorker.instances[1]!.send({ ok: true, result: { values: [[3]] } });
    await expect(second).resolves.toEqual({ values: [[3]] });
    expect(old.terminate).toHaveBeenCalledOnce();
  });

  it("无响应超过五秒会实际 terminate，dispose 后不能创建新线程", async () => {
    vi.useFakeTimers();
    const client = createFormulaTrialClient();
    const promise = client.calculate(request);
    const rejected = expect(promise).rejects.toMatchObject({ code: "TIMEOUT" });
    await vi.advanceTimersByTimeAsync(TRIAL_LIMITS.timeoutMs);
    await rejected;
    expect(FakeWorker.instances[0]!.terminate).toHaveBeenCalledOnce();
    expect(vi.getTimerCount()).toBe(0);
    client.dispose();
    await expect(client.calculate(request)).rejects.toMatchObject({ code: "CANCELLED" });
    expect(FakeWorker.instances).toHaveLength(1);
  });

  it("取消/关闭页面终止正在运行的线程", async () => {
    const client = createFormulaTrialClient();
    const promise = client.calculate(request);
    client.dispose();
    await expect(promise).rejects.toMatchObject({ code: "CANCELLED" });
    expect(FakeWorker.instances[0]!.terminate).toHaveBeenCalledOnce();
  });

  it.each(["construction", "error", "messageerror", "post", "termination"])("模块的%s失败均结束等待，不暴露底层异常", async (kind) => {
    FakeWorker.failConstruction = kind === "construction";
    FakeWorker.failPost = kind === "post";
    const client = createFormulaTrialClient();
    const promise = client.calculate(request);
    const worker = FakeWorker.instances[0];
    if (kind === "error") worker!.onerror?.(new Event("error"));
    if (kind === "messageerror") worker!.onmessageerror?.(new Event("messageerror"));
    if (kind === "termination") {
      worker!.terminate.mockImplementation(() => { throw new Error("private termination detail"); });
      worker!.send({ ok: true, result: { values: [[3]] } });
    }
    const error = await promise.catch((error: unknown) => error);
    expect(error).toMatchObject({ code: kind === "messageerror" || kind === "post" ? "INVALID" : "WORKER" });
    expect(String(error)).not.toContain("private");
  });
});
