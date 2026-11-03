import { describe, expect, it } from "vitest";
import { createSSRApp, h } from "vue";
import { renderToString } from "vue/server-renderer";

import CatalogGameCard from "./CatalogGameCard.vue";

const project = {
  title: "验收游戏",
  href: "https://game.invalid/",
  cover: "/uploads/fixture/content",
  heat: 12,
  wanted: false,
};

describe("目录封面资源优先级", () => {
  it("显式首图标记传到实际图片，原有链接和评分插槽保留", async () => {
    const html = await renderToString(createSSRApp({
      render: () => h(CatalogGameCard, { ...project, eager: true, highPriority: true }, {
        rating: () => h("span", { class: "fixture-rating" }, "AI评分 7/10"),
      }),
    }));
    expect(html).toContain('loading="eager"');
    expect(html).toContain('fetchpriority="high"');
    expect(html).toContain('href="https://game.invalid/"');
    expect(html).toContain("AI评分 7/10");
  });

  it("旧调用不传新标记时继续懒加载，不添加高优先级", async () => {
    const html = await renderToString(createSSRApp({ render: () => h(CatalogGameCard, project) }));
    expect(html).toContain('loading="lazy"');
    expect(html).not.toContain("fetchpriority=");
  });
});
