import { afterEach, describe, expect, it, vi } from "vitest";

/** 隔离浏览器偏好；不访问真实账号存储、接口或数据库。 */
async function loadLocale(language = "zh-CN", stored: string | null = null, storageFails = false) {
  vi.resetModules();
  const localStorage = {
    getItem: vi.fn(() => { if (storageFails) throw new Error("blocked"); return stored; }),
    setItem: vi.fn(() => { if (storageFails) throw new Error("blocked"); }),
  };
  vi.stubGlobal("window", { navigator: { language }, localStorage });
  vi.stubGlobal("document", { documentElement: { lang: "" }, createElement: vi.fn(() => ({})) });
  return { ...(await import("./locale")), localStorage };
}

afterEach(() => vi.unstubAllGlobals());

describe("界面语言偏好与资源", () => {
  it("首次英文浏览器使用英文，其他未支持浏览器回退中文", async () => {
    expect((await loadLocale("en-GB")).currentLocale.value).toBe("en-US");
    expect(document.documentElement.lang).toBe("en-US");
    expect((await loadLocale("fr-FR")).currentLocale.value).toBe("zh-CN");
  });

  it("手选优先于浏览器，切换同步文档和浏览器存储，非法值不覆盖偏好", async () => {
    const locale = await loadLocale("en-US", "zh-CN");
    expect(locale.currentLocale.value).toBe("zh-CN");
    locale.setLocale("en-US");
    expect(locale.currentLocale.value).toBe("en-US");
    expect(document.documentElement.lang).toBe("en-US");
    expect(locale.localStorage.setItem).toHaveBeenCalledWith("parallellines.locale", "en-US");
    locale.setLocale("invalid");
    expect(locale.currentLocale.value).toBe("en-US");
  });

  it("存储受限仍可本页切换并明确暴露未持久化状态", async () => {
    const locale = await loadLocale("en-US", null, true);
    expect(locale.currentLocale.value).toBe("en-US");
    expect(locale.localePersistenceAvailable.value).toBe(false);
    expect(() => locale.setLocale("zh-CN")).not.toThrow();
    expect(locale.currentLocale.value).toBe("zh-CN");
    expect(locale.localePersistenceAvailable.value).toBe(false);
  });

  it("中英文参数语序正确，未收录内容和业务名称保持原文", async () => {
    const locale = await loadLocale();
    expect(locale.uiText("正在查看{name}的作品", { name: "小明" })).toBe("正在查看小明的作品");
    locale.setLocale("en-US");
    expect(locale.uiText("正在查看{name}的作品", { name: "小明" })).toBe("Games by 小明");
    expect(locale.uiText("用户原始标题：{count}")).toBe("用户原始标题：{count}");
    expect(locale.uiText("__proto__")).toBe("__proto__");
    expect(locale.uiText("constructor")).toBe("constructor");
    expect(locale.uiText("{count} 个游戏", { count: 0 })).toBe("0 games");
    expect(locale.builtinSiteText("admin.nav.dashboard", "工作台", "en-US")).toBe("Dashboard");
    expect(locale.builtinSiteText("account.status.silenced", "禁言", "en-US")).toBe("Silenced");
    expect(locale.uiText("禁言")).toBe("Silence");
    expect(locale.builtinSiteText("profile.activity", "活动", "en-US")).toBe("Activity");
    expect(locale.uiText("活动")).toBe("Events");
    expect(locale.builtinSiteText("topic.pinned", "置顶", "en-US")).toBe("Pinned");
    expect(locale.uiText("置顶")).toBe("Pin");
    expect(locale.builtinSiteText("tools.undo", "撤销", "en-US")).toBe("Undo");
    expect(locale.uiText("撤销")).toBe("Revoke");
  });

  it("静态路由源在同页切换后重新生成标题与说明，不缓存首次语言", async () => {
    const locale = await loadLocale("en-US");
    const { buildSeoSiteDescription } = await import("@/shared/seo/structuredData");
    const { resolveRouteSeoMeta } = await import("@/shared/seo/meta");
    const route = { title: "个人中心 · {siteTitle}", description: buildSeoSiteDescription("{siteName}") };
    const context = { routePath: "/account", siteTitle: "品牌原名", siteName: "品牌原名", siteTagline: "发现游戏、工具与创意" };
    expect(resolveRouteSeoMeta(route, context).title).toBe("My account · 品牌原名");
    expect(resolveRouteSeoMeta(route, context).description).toContain("is a place to discover games");
    locale.setLocale("zh-CN");
    expect(resolveRouteSeoMeta(route, context).title).toBe("个人中心 · 品牌原名");
    expect(resolveRouteSeoMeta(route, context).description).toContain("是发现游戏、实用工具");
    expect(resolveRouteSeoMeta(route, context).locale).toBe("zh_CN");
  });
});
