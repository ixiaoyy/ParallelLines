import { beforeEach, afterEach, describe, it, expect, vi } from 'vitest';
import { createWorkbookClient } from '../localWorkbookClient';
import type { LocalWorkbook, OperationResult } from '../localProcessingModel';

class FakeWorker {
  static instances: FakeWorker[] = [];
  static constructionError: Error | undefined;
  static postError: Error | undefined;
  onmessage: ((event: MessageEvent<unknown>) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onmessageerror: ((event: MessageEvent<unknown>) => void) | null = null;
  terminated = 0;
  sent: Array<{ request: unknown; transfer: Transferable[] }> = [];
  constructor(readonly url: URL, readonly options: WorkerOptions) {
    if (FakeWorker.constructionError) throw FakeWorker.constructionError;
    FakeWorker.instances.push(this);
  }
  postMessage(request: unknown, transfer: Transferable[] = []) {
    if (FakeWorker.postError) throw FakeWorker.postError;
    this.sent.push({ request, transfer });
  }
  terminate() { this.terminated += 1; }
  message(data: unknown) { this.onmessage?.(new MessageEvent<unknown>('message', { data })); }
  error() { this.onerror?.(new Event('error')); }
  messageError() { this.onmessageerror?.(new MessageEvent<unknown>('messageerror')); }
}

const workbook: LocalWorkbook = { sourceName: 'artificial.xlsx', sheets: [{ name: '人工', rows: [['ID'], ['001']], warnings: [] }] };
const result: OperationResult = {
  kind: 'clean', headers: ['ID'], rows: [['001']], rowNumbers: [2], columnCount: 1,
  summary: { inputRows: 1, outputRows: 1, changedCells: 0, removedRows: 0, matchedRows: 0, usedNumericRows: 0, blankNumericRows: 0 }, issues: [],
};
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
class ControlledFile extends File {
  readonly readBuffer = vi.fn<() => Promise<ArrayBuffer>>();
  constructor(read: () => Promise<ArrayBuffer>, name: string, size: number) {
    super([new Uint8Array(size)], name, { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
    this.readBuffer.mockImplementation(read);
  }
  override arrayBuffer(): Promise<ArrayBuffer> { return this.readBuffer(); }
}
function file(read = () => Promise.resolve(new ArrayBuffer(12)), name = 'artificial.xlsx', size = 12): ControlledFile {
  return new ControlledFile(read, name, size);
}
const tick = async () => { await vi.advanceTimersByTimeAsync(0); };
const worker = (): FakeWorker => {
  const instance = FakeWorker.instances.at(-1);
  if (!instance) throw new Error('No artificial worker was constructed');
  return instance;
};

beforeEach(() => {
  vi.useFakeTimers();
  FakeWorker.instances = [];
  FakeWorker.constructionError = undefined;
  FakeWorker.postError = undefined;
  vi.stubGlobal('Worker', FakeWorker);
});
afterEach(() => { vi.clearAllTimers(); vi.useRealTimers(); vi.unstubAllGlobals(); });

describe('createWorkbookClient candidate lifecycle', () => {
  it('reads a valid response and transfers the original file buffer', async () => {
    const client = createWorkbookClient();
    const bytes = new ArrayBuffer(12);
    const pending = client.read(file(() => Promise.resolve(bytes)));
    await tick();
    expect(worker().sent).toEqual([{ request: { kind: 'read', buffer: bytes, sourceName: 'artificial.xlsx' }, transfer: [bytes] }]);
    expect(worker().url.href).toContain('localWorkbook.worker.ts');
    worker().message({ ok: true, kind: 'read', workbook });
    await expect(pending).resolves.toEqual(workbook);
    expect(worker().terminated).toBe(1);
    expect(vi.getTimerCount()).toBe(0);
  });

  it('writes a valid response without transferring the current preview', async () => {
    const client = createWorkbookClient();
    const pending = client.write(result, '人工');
    expect(worker().sent).toEqual([{ request: { kind: 'write', result, sheetName: '人工' }, transfer: [] }]);
    const bytes = new ArrayBuffer(30);
    worker().message({ ok: true, kind: 'write', buffer: bytes });
    await expect(pending).resolves.toBe(bytes);
    expect(worker().terminated).toBe(1);
  });

  it.each([
    ['not-xlsx.csv', 12, '只支持'], ['artificial.xlsx', 0, '为空'], ['artificial.xlsx', 5 * 1024 * 1024 + 1, '超过 5 MB'],
  ])('rejects invalid metadata before reading: %s', async (name, size, message) => {
    const candidate = file(undefined, name, size);
    await expect(createWorkbookClient().read(candidate)).rejects.toThrow(message);
    expect(candidate.readBuffer).not.toHaveBeenCalled();
    expect(FakeWorker.instances).toHaveLength(0);
  });

  it('cancel terminates a running worker once and settles its request', async () => {
    const client = createWorkbookClient();
    const pending = client.write(result, '人工');
    const failure = expect(pending).rejects.toThrow('已取消');
    const previous = worker();
    client.cancel(); client.cancel();
    await failure;
    expect(previous.terminated).toBe(1);
    expect(vi.getTimerCount()).toBe(0);
  });

  it('dispose cancels current work and permanently rejects future reads/writes', async () => {
    const client = createWorkbookClient();
    const pending = client.write(result, '人工');
    const failure = expect(pending).rejects.toThrow('已取消');
    client.dispose(); client.dispose();
    await failure;
    await expect(client.read(file())).rejects.toThrow('已关闭');
    await expect(client.write(result, '人工')).rejects.toThrow('已关闭');
    expect(FakeWorker.instances).toHaveLength(1);
  });

  it.each(['cancel', 'dispose'] as const)('%s settles even while file.arrayBuffer is still pending', async (action) => {
    const client = createWorkbookClient();
    const delayed = deferred<ArrayBuffer>();
    let outcome = 'pending';
    const pending = client.read(file(() => delayed.promise));
    const observed = pending.then(() => { outcome = 'resolved'; }, (error: unknown) => { outcome = error instanceof Error ? error.message : String(error); });
    client[action]();
    await tick();
    const stateAfterCancel = outcome;
    delayed.resolve(new ArrayBuffer(12));
    await observed;
    expect(stateAfterCancel).toContain('已取消');
    expect(FakeWorker.instances).toHaveLength(0);
  });

  it('a delayed cancelled file cannot replace or cancel a newer file', async () => {
    const client = createWorkbookClient();
    const delayed = deferred<ArrayBuffer>();
    const old = client.read(file(() => delayed.promise, 'old.xlsx'));
    const oldFailure = expect(old).rejects.toThrow('已取消');
    const current = client.read(file(undefined, 'new.xlsx'));
    await tick();
    const currentWorker = worker();
    delayed.resolve(new ArrayBuffer(12));
    await oldFailure;
    expect(currentWorker.terminated).toBe(0);
    currentWorker.message({ ok: true, kind: 'read', workbook });
    await expect(current).resolves.toEqual(workbook);
    expect(FakeWorker.instances).toHaveLength(1);
  });

  it('new work cancels old work and stale/duplicate messages cannot settle the new job', async () => {
    const client = createWorkbookClient();
    const old = client.write(result, 'old');
    const oldFailure = expect(old).rejects.toThrow('已取消');
    const previous = worker();
    const current = client.write(result, 'new');
    const currentWorker = worker();
    previous.message({ ok: true, kind: 'write', buffer: new ArrayBuffer(1) });
    await oldFailure;
    expect(currentWorker.terminated).toBe(0);
    const bytes = new ArrayBuffer(2);
    currentWorker.message({ ok: true, kind: 'write', buffer: bytes });
    currentWorker.message({ ok: false, message: 'late error' });
    await expect(current).resolves.toBe(bytes);
    expect(currentWorker.terminated).toBe(1);
  });

  it('times out a worker at 20 seconds and terminates it', async () => {
    const pending = createWorkbookClient().write(result, '人工');
    const failure = expect(pending).rejects.toThrow('超过 20 秒');
    await vi.advanceTimersByTimeAsync(20_000);
    await failure;
    expect(worker().terminated).toBe(1);
    expect(vi.getTimerCount()).toBe(0);
  });

  it('times out a file read that never produces a buffer', async () => {
    const delayed = deferred<ArrayBuffer>();
    let outcome = 'pending';
    const pending = createWorkbookClient().read(file(() => delayed.promise));
    const observed = pending.then(() => { outcome = 'resolved'; }, (error: unknown) => { outcome = error instanceof Error ? error.message : String(error); });
    await vi.advanceTimersByTimeAsync(20_000);
    const stateAfterTimeout = outcome;
    delayed.resolve(new ArrayBuffer(12));
    await tick();
    if (FakeWorker.instances.length) worker().message({ ok: true, kind: 'read', workbook });
    await observed;
    expect(stateAfterTimeout).toContain('超过 20 秒');
    expect(FakeWorker.instances).toHaveLength(0);
  });

  it('shares the 20-second budget between the file read and worker', async () => {
    const delayed = deferred<ArrayBuffer>();
    const pending = createWorkbookClient().read(file(() => delayed.promise));
    const failure = expect(pending).rejects.toThrow('超过 20 秒');
    await vi.advanceTimersByTimeAsync(15_000);
    delayed.resolve(new ArrayBuffer(12));
    await tick();
    expect(FakeWorker.instances).toHaveLength(1);
    await vi.advanceTimersByTimeAsync(5_000);
    await failure;
    expect(worker().terminated).toBe(1);
  });

  it('handles a rejected file read without creating a worker or retaining a timer', async () => {
    const pending = createWorkbookClient().read(file(() => Promise.reject(new Error('Artificial file failure'))));
    await expect(pending).rejects.toThrow('读取所选文件失败');
    expect(FakeWorker.instances).toHaveLength(0);
    expect(vi.getTimerCount()).toBe(0);
  });

  it('converts construction failure to the actionable module error', async () => {
    FakeWorker.constructionError = new Error('SecurityError artificial');
    await expect(createWorkbookClient().write(result, '人工')).rejects.toThrow('文件处理模块加载失败');
    expect(vi.getTimerCount()).toBe(0);
  });

  it('handles postMessage failure and allows the next operation to work', async () => {
    FakeWorker.postError = new Error('DataCloneError artificial');
    const client = createWorkbookClient();
    await expect(client.write(result, '人工')).rejects.toThrow('无法启动文件处理');
    expect(worker().terminated).toBe(1);
    FakeWorker.postError = undefined;
    const next = client.write(result, '人工');
    worker().message({ ok: true, kind: 'write', buffer: new ArrayBuffer(2) });
    await expect(next).resolves.toHaveProperty('byteLength', 2);
  });

  it.each([['error', '模块加载失败'], ['messageError', '结果无法读取']] as const)('handles worker %s', async (action, message) => {
    const pending = createWorkbookClient().write(result, '人工');
    const failure = expect(pending).rejects.toThrow(message);
    worker()[action]();
    await failure;
    expect(worker().terminated).toBe(1);
    expect(vi.getTimerCount()).toBe(0);
  });

  it('preserves the worker export validation error', async () => {
    const pending = createWorkbookClient().write(result, '人工');
    worker().message({ ok: false, message: '存在无效金额，无法导出。' });
    await expect(pending).rejects.toThrow('存在无效金额，无法导出。');
  });

  it('rejects success for the wrong operation kind', async () => {
    const pending = createWorkbookClient().write(result, '人工');
    worker().message({ ok: true, kind: 'read', workbook });
    await expect(pending).rejects.toThrow('导出结果无效');
  });

  it.each([null, undefined, {}, { ok: false }, { ok: true, kind: 'write', buffer: 'not a buffer' }])('rejects malformed responses without throwing from the event handler: %j', async (response) => {
    const pending = createWorkbookClient().write(result, '人工');
    const observed = pending.catch((error: unknown) => error);
    expect(() => worker().message(response)).not.toThrow();
    const error = await observed;
    expect(error).toBeInstanceOf(Error);
    if (!(error instanceof Error)) throw new Error('Expected a rejected Error result');
    expect(error.message).toMatch(/结果无效|结果无法读取/);
    expect(worker().terminated).toBe(1);
    expect(vi.getTimerCount()).toBe(0);
  });

  it('rejects a read response with no workbook', async () => {
    const pending = createWorkbookClient().read(file());
    await tick();
    worker().message({ ok: true, kind: 'read', workbook: null });
    await expect(pending).rejects.toThrow('读取结果无效');
  });
});
