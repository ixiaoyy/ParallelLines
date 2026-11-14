import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  beginCircleTransaction, FLOW_STORAGE_KEY, isUnifiedStatusMessage, localReturnPath,
  mainAuthOrigin, readCircleTransaction, statusClientOrigin,
} from "./protocol";
import { isUnifiedSsoContinuation, resolveAuthReturn } from "@/shared/router/authReturn";

function memoryStorage(): Storage {
  const data = new Map<string, string>();
  return { get length() { return data.size; }, clear: () => data.clear(), key: index => [...data.keys()][index] ?? null,
    getItem: key => data.get(key) ?? null, removeItem: key => { data.delete(key); }, setItem: (key, value) => { data.set(key, value); } };
}

describe("统一登录浏览器协议", () => {
  beforeEach(() => { vi.stubEnv("VITE_UNIFIED_MAIN_ORIGIN", ""); vi.stubEnv("VITE_UNIFIED_CIRCLE_ORIGIN", ""); });
  afterEach(() => vi.unstubAllEnvs());
  it("只接受固定正式来源或显式回环开发来源", () => {
    expect(mainAuthOrigin()).toBe("https://pingxingxian.space");
    vi.stubEnv("VITE_UNIFIED_MAIN_ORIGIN", "https://evil.example");
    expect(() => mainAuthOrigin()).toThrow();
    vi.stubEnv("VITE_UNIFIED_MAIN_ORIGIN", "http://127.0.0.1:4183");
    expect(mainAuthOrigin()).toBe("http://127.0.0.1:4183");
    vi.stubEnv("VITE_UNIFIED_CIRCLE_ORIGIN", "http://127.0.0.1:4184");
    expect(statusClientOrigin("circle")).toBe("http://127.0.0.1:4184");
    vi.stubEnv("VITE_UNIFIED_CIRCLE_ORIGIN", "https://forum.pingxingxian.space/auth");
    expect(() => statusClientOrigin("circle")).toThrow();
  });
  it.each(["//evil.example/", "/%2f%2fevil.example", "/a/../auth", "/%61uth", "/auth/unified/logout?ticket=x", "/api/v1/me", "/a\\b"])("拒绝危险或协议回跳 %s", path => {
    expect(localReturnPath(path, "https://forum.pingxingxian.space")).toBe("/");
  });
  it("保留正常论坛查询、中文空格与锚点", () => {
    expect(localReturnPath("/search?q=hello%20world#replies", "https://forum.pingxingxian.space")).toBe("/search?q=hello%20world#replies");
    expect(localReturnPath("/search?q=100%25", "https://forum.pingxingxian.space")).toBe("/search?q=100%25");
  });
  it("登录后只允许授权入口，禁止状态/退出页成为接续", () => {
    const origin = "https://pingxingxian.space";
    expect(isUnifiedSsoContinuation("/auth/unified?state=abcd", origin)).toBe(true);
    expect(resolveAuthReturn("/auth/unified/logout?ticket=bad", origin, "/")).toBe("/");
    expect(isUnifiedSsoContinuation("https://evil.example/auth/unified", origin)).toBe(false);
  });
  it("状态回信匹配随机request_id，断连与匿名是不同状态", () => {
    const base = { type: "pl:unified-session", version: 1, request_id: "a".repeat(32), available: false,
      authenticated: false, subject: null, auth_epoch: null };
    expect(isUnifiedStatusMessage(base, "a".repeat(32))).toBe(true);
    expect(isUnifiedStatusMessage(base, "b".repeat(32))).toBe(false);
    expect(isUnifiedStatusMessage({ ...base, authenticated: true }, base.request_id)).toBe(false);
    expect(isUnifiedStatusMessage({ ...base, available: "true" }, base.request_id)).toBe(false);
  });
  it("PKCE/verifier仅存标签会话，state/有效期/模式必须匹配", async () => {
    const storage = memoryStorage();
    const { transaction, challenge } = await beginCircleTransaction("/topics/1", "https://forum.pingxingxian.space", storage, "silent");
    expect(challenge).toMatch(/^[A-Za-z0-9_-]{43}$/);
    expect(transaction.verifier).toMatch(/^[A-Za-z0-9_-]{43}$/);
    expect(readCircleTransaction(transaction.state, storage).mode).toBe("silent");
    expect(() => readCircleTransaction("b".repeat(32), storage)).toThrow();
    expect(() => readCircleTransaction(transaction.state, storage, transaction.createdAt + 900_001)).toThrow();
    storage.setItem(FLOW_STORAGE_KEY, JSON.stringify({ ...transaction, mode: "other" }));
    expect(() => readCircleTransaction(transaction.state, storage)).toThrow();
  });
  it("存储拒绝时不继续无状态授权", async () => {
    const storage = memoryStorage();
    storage.setItem = () => { throw new Error("disabled"); };
    await expect(beginCircleTransaction("/", "https://forum.pingxingxian.space", storage)).rejects.toThrow();
  });
});
