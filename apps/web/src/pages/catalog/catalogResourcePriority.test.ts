// 使用 vitest.catalog-resources.config.ts，保留公开图片 URL，独立验证 SSR 图片加载属性。
import { describe, expect, it } from "vitest";
import { createSSRApp, h } from "vue";
import { renderToString } from "vue/server-renderer";

import CatalogGameCard from "./CatalogGameCard.vue";
import CatalogLeaderboard from "./CatalogLeaderboard.vue";

const project = {
  title: "验收游戏",
  href: "https://game.invalid/",
  cover: "/uploads/fixture/content",
  heat: 12,
  wanted: false,
};

describe("目录封面资源优先级", () => {
  it("显式首图标记传到实际图片，悬停层只保留名称", async () => {
    const html = await renderToString(createSSRApp({
      render: () => h(CatalogGameCard, { ...project, eager: true, highPriority: true }, {
        rating: () => h("span", { class: "fixture-rating" }, "AI评分 7/10"),
      }),
    }));
    expect(html).toContain('loading="eager"');
    expect(html).toContain('fetchpriority="high"');
    expect(html).toContain('href="https://game.invalid/"');
    expect(html).toContain("验收游戏");
    expect(html).not.toContain("AI评分 7/10");
    expect(html).not.toContain("热度");
  });

  it("旧调用不传新标记时继续懒加载，不添加高优先级", async () => {
    const html = await renderToString(createSSRApp({ render: () => h(CatalogGameCard, project) }));
    expect(html).toContain('loading="lazy"');
    expect(html).not.toContain("fetchpriority=");
  });

  it("榜单前三名作品及时加载，后续作品和奖牌装饰继续懒加载", async () => {
    const html = await renderToString(createSSRApp({
      render: () => h(CatalogLeaderboard, {
        title: "作者榜",
        entries: [
          { key: "first", name: "首位作者", rank: 1, cover: "/first.webp", metric: "3 个作品" },
          { key: "fourth", name: "后续作者", rank: 4, cover: "/fourth.webp", metric: "1 个作品" },
        ],
        hasMore: false,
        moreLabel: "加载更多作者",
      }),
    }));
    const images = html.match(/<img\b[^>]*>/g) ?? [];
    expect(images.find((image) => image.includes('src="/first.webp"'))).toContain('loading="eager"');
    expect(images.find((image) => image.includes('src="/fourth.webp"'))).toContain('loading="lazy"');
    const ornaments = images.filter((image) => image.includes("/catalog/night-arcade-v1/"));
    expect(ornaments.length).toBeGreaterThan(0);
    expect(ornaments.every((image) => image.includes('loading="lazy"') && image.includes('fetchpriority="low"'))).toBe(true);
  });
});
