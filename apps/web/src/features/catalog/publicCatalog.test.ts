import { afterEach, describe, expect, it, vi } from "vitest";
import { apiGet, publicApiGet } from "@/shared/api/client";
import { fetchCatalogCategoryPage, fetchCatalogOverview } from "./api";

afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });

describe("公开目录请求边界", () => {
  it("允许浏览器缓存，不读取本地身份、不携带Cookie或访客头", async () => {
    const getItem = vi.fn(() => "private-token");
    vi.stubGlobal("window", { localStorage: { getItem } });
    const fetch = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => new Response(JSON.stringify({ data: { ok: true } }), { status: 200 }));
    vi.stubGlobal("fetch", fetch);
    expect(await publicApiGet("/catalog/overview")).toEqual({ ok: true });
    const init = fetch.mock.calls[0]?.[1] as RequestInit;
    expect(init.credentials).toBe("omit"); expect(init.cache).toBe("default");
    expect(new Headers(init.headers).get("Authorization")).toBeNull();
    expect(new Headers(init.headers).get("X-ParallelLines-Visitor")).toBeNull();
    expect(getItem).not.toHaveBeenCalled();
  });
  it("省略专题与明确空专题不同；分类按真实limit和游标请求", async () => {
    const fetch = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => new Response(JSON.stringify({ data: {} }), { status: 200 }));
    vi.stubGlobal("fetch", fetch);
    await fetchCatalogOverview(undefined, 0);
    await fetchCatalogOverview([], 0);
    await fetchCatalogCategoryPage("real-slug", 13, "opaque+/=", ["first", "second"]);
    const urls = fetch.mock.calls.map((call) => new URL(String(call[0])));
    expect(urls[0]!.searchParams.has("hero_slugs")).toBe(false);
    expect(urls[1]!.searchParams.get("hero_slugs")).toBe("");
    expect(urls[2]!.searchParams.get("limit")).toBe("13");
    expect(urls[2]!.searchParams.get("cursor")).toBe("opaque+/=");
    expect(urls[2]!.searchParams.get("priority_slugs")).toBe("first,second");
  });
  it("沿用API错误边界，不以失败的公开接口回退全量", async () => {
    const fetch = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => new Response(JSON.stringify({ error: { code: "not_found", message: "missing" } }), { status: 404 }));
    vi.stubGlobal("fetch", fetch);
    await expect(fetchCatalogOverview(undefined, 0)).rejects.toMatchObject({ code: "not_found", status: 404 });
    expect(fetch).toHaveBeenCalledTimes(1);
  });
  it("调用方取消会传到真实fetch，旧apiGet仍保持no-cache", async () => {
    const fetch = vi.fn(async (_url: unknown, init?: RequestInit) => {
      if (String(_url).endsWith("/legacy")) return new Response(JSON.stringify({ data: {} }), { status: 200 });
      return new Promise<Response>((_resolve, reject) => init?.signal?.addEventListener("abort", () => reject(new DOMException("cancelled", "AbortError")), { once: true }));
    });
    vi.stubGlobal("fetch", fetch);
    const controller = new AbortController();
    const request = publicApiGet("/catalog/overview", controller.signal);
    const rejection = expect(request).rejects.toMatchObject({ name: "AbortError" });
    controller.abort(); await rejection;
    await apiGet("/legacy");
    expect(fetch.mock.calls[1]?.[1]?.cache).toBe("no-cache");
  });
});
