import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({ fetchUnifiedState: vi.fn(), bootstrapUnified: vi.fn(), refreshLegacyMainAccess: vi.fn() }));
vi.mock("./api", async original => ({ ...(await original<typeof import("./api")>()), ...api }));

const data = new Map<string, string>();
const storage = { getItem: (key: string) => data.get(key) ?? null, setItem: (key: string, value: string) => data.set(key, value), removeItem: (key: string) => data.delete(key) };
function access(subject: string) {
  return { authenticated: true as const, subject, auth_epoch: subject.repeat(32), access_token: subject + ".token", token_type: "bearer" as const,
    expires_in: 300, session_id: subject + "-sid", user: { id: subject, username: subject } as import("../model").UserPublic };
}
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>(done => { resolve = done; });
  return { promise, resolve };
}

describe("Main权威会话与切换", () => {
  beforeEach(() => {
    vi.resetModules(); vi.clearAllMocks(); data.clear();
    vi.stubEnv("VITE_UNIFIED_AUTH_ENABLED", "true");
    vi.stubGlobal("localStorage", storage);
    const window = Object.assign(new EventTarget(), { localStorage: storage, location: { pathname: "/" }, clearTimeout, setTimeout });
    vi.stubGlobal("window", window);
    vi.stubGlobal("BroadcastChannel", undefined);
  });
  afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); vi.unstubAllEnvs(); });
  it("中央cookie身份优先，绝不拿磁盘另一身份覆盖", async () => {
    data.set("parallellines.access_token", "legacy-B"); data.set("parallellines.refresh_token", "refresh-B");
    api.fetchUnifiedState.mockResolvedValue({ authenticated: true, subject: "A", auth_epoch: "A".repeat(32) });
    api.bootstrapUnified.mockResolvedValue(access("A"));
    const session = await import("./session");
    await session.ensurePrimarySession();
    expect(api.bootstrapUnified).toHaveBeenCalledWith();
    expect(api.refreshLegacyMainAccess).not.toHaveBeenCalled();
    expect(session.currentUnifiedState().subject).toBe("A");
    expect(data.has("parallellines.refresh_token")).toBe(false);
  });
  it("无中央cookie的旧会话，access过期只刷新原会话一次", async () => {
    data.set("parallellines.access_token", "expired"); data.set("parallellines.refresh_token", "refresh-A");
    const { UnifiedApiError } = await import("./api");
    api.fetchUnifiedState.mockResolvedValue({ authenticated: false, subject: null, auth_epoch: null });
    api.bootstrapUnified.mockRejectedValueOnce(new UnifiedApiError("expired", "expired", 401)).mockResolvedValueOnce(access("A"));
    api.refreshLegacyMainAccess.mockResolvedValue("renewed-A");
    const session = await import("./session"); await session.ensurePrimarySession();
    expect(api.refreshLegacyMainAccess).toHaveBeenCalledExactlyOnceWith("refresh-A");
    expect(api.bootstrapUnified.mock.calls).toEqual([[false, "expired"], [false, "renewed-A"]]);
  });
  it("中央状态失败不以旧refresh降级、不伪装退出", async () => {
    data.set("parallellines.refresh_token", "refresh-A");
    api.fetchUnifiedState.mockRejectedValue(new Error("unavailable"));
    const session = await import("./session");
    await expect(session.ensurePrimarySession()).rejects.toThrow("unavailable");
    expect(api.bootstrapUnified).not.toHaveBeenCalled(); expect(api.refreshLegacyMainAccess).not.toHaveBeenCalled();
    expect(session.unifiedAvailability.value).toBe("unavailable");
  });
  it("显式B登录完成后，先前A状态的迟到结果不能回填", async () => {
    const old = deferred<ReturnType<typeof access>>();
    api.fetchUnifiedState.mockResolvedValue({ authenticated: true, subject: "A", auth_epoch: "A".repeat(32) });
    api.bootstrapUnified.mockImplementation((replace: boolean) => replace ? Promise.resolve(access("B")) : old.promise);
    const session = await import("./session");
    const pending = session.ensurePrimarySession(); await vi.waitFor(() => expect(api.bootstrapUnified).toHaveBeenCalled());
    await session.completePrimaryLogin("proof-B"); old.resolve(access("A")); await pending;
    expect(session.currentUnifiedState().subject).toBe("B");
    const { queryClient } = await import("@/shared/api/queryClient");
    expect(queryClient.getQueryData(["auth", "me"])).toMatchObject({ id: "B" });
  });
  it("旧缓存清理比新切换更晚完成也不能覆盖新账号", async () => {
    const session = await import("./session"); const { queryClient } = await import("@/shared/api/queryClient");
    const cancelA = deferred<void>();
    vi.spyOn(queryClient, "cancelQueries").mockImplementationOnce(() => cancelA.promise).mockResolvedValueOnce();
    const old = session.applyUnifiedAccess(access("A"));
    await session.applyUnifiedAccess(access("B")); cancelA.resolve(); await old;
    expect(queryClient.getQueryData(["auth", "me"])).toMatchObject({ id: "B" });
  });
  it("另一主站标签换号通知不丢失，旧A在途成功也不能回填", async () => {
    const old = deferred<ReturnType<typeof access>>();
    api.fetchUnifiedState.mockResolvedValueOnce({ authenticated: true, subject: "A", auth_epoch: "A".repeat(32) })
      .mockResolvedValue({ authenticated: true, subject: "B", auth_epoch: "B".repeat(32) });
    api.bootstrapUnified.mockReturnValueOnce(old.promise).mockResolvedValue(access("B"));
    const session = await import("./session"); const { queryClient } = await import("@/shared/api/queryClient");
    const write = vi.spyOn(queryClient, "setQueryData");
    const stop = session.startUnifiedBrowserSession();
    await vi.waitFor(() => expect(api.bootstrapUnified).toHaveBeenCalledTimes(1));
    window.dispatchEvent(new Event("pl:unified-auth-change"));
    old.resolve(access("A"));
    await vi.waitFor(() => expect(session.currentUnifiedState().subject).toBe("B"));
    expect(api.fetchUnifiedState).toHaveBeenCalledTimes(2);
    expect(write.mock.calls.some(([, value]) => typeof value === "object" && value !== null && "id" in value && value.id === "A")).toBe(false);
    stop();
  });
});
