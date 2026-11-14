import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const storage = new Map<string, string>();
const localStorage = { getItem: (key: string) => storage.get(key) ?? null, setItem: (key: string, value: string) => storage.set(key, value), removeItem: (key: string) => storage.delete(key) };
const ok = (value: unknown) => new Response(JSON.stringify({ data: value }), { status: 200, headers: { "Content-Type": "application/json" } });
const unauthorized = () => new Response(JSON.stringify({ error: { code: "invalid_token", message: "expired" } }), { status: 401 });

describe("API账号隔离与短令牌续发", () => {
  beforeEach(() => { vi.resetModules(); storage.clear(); vi.stubGlobal("window", { localStorage }); });
  afterEach(() => vi.unstubAllGlobals());
  it("统一短token不保存refresh，磁盘其他账号不能悄悄改本页身份", async () => {
    const client = await import("@/shared/api/client");
    client.setAuthTokens("legacy", "refresh");
    client.setSessionAccessToken("A");
    expect(client.getRefreshToken()).toBeNull();
    localStorage.setItem("parallellines.access_token", "B");
    expect(client.getAccessToken()).toBe("A");
  });
  it("没有refresh的统一会话401仍可同身份续发一次", async () => {
    const client = await import("@/shared/api/client");
    client.setApiIdentityContext("A"); client.setSessionAccessToken("A1");
    const renew = vi.fn(async () => { client.setSessionAccessToken("A2"); return "A2"; });
    client.registerSessionAccessRefresher(renew);
    const fetch = vi.fn().mockResolvedValueOnce(unauthorized()).mockResolvedValueOnce(ok("done"));
    vi.stubGlobal("fetch", fetch);
    expect(await client.apiRequest("/auth/me")).toBe("done");
    expect(renew).toHaveBeenCalledTimes(1); expect(fetch).toHaveBeenCalledTimes(2);
    expect(fetch.mock.calls[1][1].headers.get("Authorization")).toBe("Bearer A2");
  });
  it.each(["apiRequest", "apiBlob", "apiRequestEnvelope"] as const)("%s不交付旧身份迟到响应", async method => {
    const client = await import("@/shared/api/client");
    client.setApiIdentityContext("A"); client.setSessionAccessToken("A1");
    let deliver!: (value: Response) => void;
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(resolve => { deliver = resolve; })));
    const pending = client[method]("/private");
    client.setApiIdentityContext("B"); client.setSessionAccessToken("B1");
    deliver(ok({ private: "A" }));
    await expect(pending).rejects.toMatchObject({ code: "identity_changed" });
  });
  it("401续发中换号不把A操作重放给B", async () => {
    const client = await import("@/shared/api/client");
    client.setApiIdentityContext("A"); client.setSessionAccessToken("A1");
    client.registerSessionAccessRefresher(async () => { client.setApiIdentityContext("B"); client.setSessionAccessToken("B1"); return "B1"; });
    const fetch = vi.fn().mockResolvedValue(unauthorized()); vi.stubGlobal("fetch", fetch);
    await expect(client.apiRequest("/posts", { method: "POST", body: "{}" })).rejects.toMatchObject({ code: "identity_changed" });
    expect(fetch).toHaveBeenCalledTimes(1);
  });
  it("新能力未注册时保留原生refresh协议", async () => {
    const client = await import("@/shared/api/client"); client.setAuthTokens("old", "legacy-refresh");
    const fetch = vi.fn().mockResolvedValueOnce(unauthorized()).mockResolvedValueOnce(ok({ access_token: "renewed", token_type: "bearer" })).mockResolvedValueOnce(ok("legacy"));
    vi.stubGlobal("fetch", fetch);
    expect(await client.apiRequest("/auth/me")).toBe("legacy");
    expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({ refresh_token: "legacy-refresh" });
    expect(client.getAccessToken()).toBe("renewed");
  });
  it("未启用统一上下文时，旧退出后仍按原规则读取别的标签新登录", async () => {
    const client = await import("@/shared/api/client"); client.setAuthTokens("old", "refresh");
    client.clearAuthTokens(); localStorage.setItem("parallellines.access_token", "other-tab-login");
    expect(client.getAccessToken()).toBe("other-tab-login");
  });
});
