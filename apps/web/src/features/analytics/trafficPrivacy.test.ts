import { afterEach, describe, expect, it, vi } from "vitest";

import { isTrafficExcluded, setTrafficExcluded } from "./trafficPrivacy";

afterEach(() => vi.unstubAllGlobals());

/** 用最小 Cookie 替身检查域、保密属性和事件通知，不访问真实浏览器资料。 */
function installCookieFixture(host: string, protocol = "https:", writable = true) {
  let value = "";
  let lastWrite = "";
  const dispatchEvent = vi.fn();
  vi.stubGlobal("document", {
    get cookie() { return value; },
    set cookie(next: string) {
      lastWrite = next;
      if (writable) value = next.includes("Max-Age=0") ? "" : next.split(";")[0];
    },
  });
  vi.stubGlobal("window", { location: { hostname: host, protocol }, dispatchEvent });
  return { dispatchEvent, lastWrite: () => lastWrite };
}

describe("当前浏览器统计排除", () => {
  it("正式子域共享匿名偏好，可恢复且每次成功后通知采集器", () => {
    const state = installCookieFixture("forum.pingxingxian.space");
    expect(setTrafficExcluded(true)).toBe(true);
    expect(isTrafficExcluded()).toBe(true);
    expect(state.lastWrite()).toContain("Domain=.pingxingxian.space");
    expect(state.lastWrite()).toContain("Secure");
    expect(state.lastWrite()).toContain("SameSite=Lax");
    expect(state.dispatchEvent.mock.calls[0][0].type).toBe("pl:traffic-preference");
    expect(setTrafficExcluded(false)).toBe(true);
    expect(isTrafficExcluded()).toBe(false);
    expect(state.lastWrite()).toContain("Max-Age=0");
    expect(state.dispatchEvent).toHaveBeenCalledTimes(2);
  });

  it("本地仅使用当前主机，不把偏好写到生产域", () => {
    const state = installCookieFixture("localhost", "http:");
    expect(setTrafficExcluded(true)).toBe(true);
    expect(state.lastWrite()).not.toContain("Domain=");
    expect(state.lastWrite()).not.toContain("Secure");
  });

  it("后缀伪装域名不会获得父域 Cookie", () => {
    const state = installCookieFixture("notpingxingxian.space");
    expect(setTrafficExcluded(true)).toBe(true);
    expect(state.lastWrite()).not.toContain("Domain=");
  });

  it("Cookie 未保存时不通知成功或假定已排除", () => {
    const state = installCookieFixture("pingxingxian.space", "https:", false);
    expect(setTrafficExcluded(true)).toBe(false);
    expect(isTrafficExcluded()).toBe(false);
    expect(state.dispatchEvent).not.toHaveBeenCalled();
  });
});
