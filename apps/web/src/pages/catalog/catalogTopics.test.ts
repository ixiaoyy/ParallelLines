import { describe, expect, it } from "vitest";

import { parseCatalogNavigation } from "./catalogNavigation";
import { catalogGameplayFor, CATALOG_MORE_TOPICS, countCatalogTopics, isCatalogTopicId, matchesCatalogTopic } from "./catalogTopics";
import type { CatalogTopicProject } from "./catalogTopics";

function project(name: string, description: string | null = null, slug = "unknown"): CatalogTopicProject {
  return { name, description, slug };
}

describe("catalog gameplay topics", () => {
  it("does not infer gameplay from internal authorship, popularity or AI score", () => {
    const unknown = { ...project("不明玩法"), authorName: "original", kind: "internal", viewCount: 999999, aiRating: { score: 10 } };
    expect(matchesCatalogTopic(unknown, "classic")).toBe(false);
    expect(matchesCatalogTopic(unknown, "quick")).toBe(false);
    expect(matchesCatalogTopic(project("Chess Cubed"), "classic")).toBe(true);
    expect(matchesCatalogTopic(project("Chess Cubed"), "quick")).toBe(false);
  });

  it("uses a concrete gameplay description even when the title is unrelated", () => {
    const city = project("CityMaker / 城市营造", "在 4×4 街区上玩 2048：合并相同建筑。");
    expect(matchesCatalogTopic(city, "classic")).toBe(true);
    expect(matchesCatalogTopic(city, "number-merging")).toBe(true);
    expect(catalogGameplayFor(city).map((rule) => rule.id)).toEqual(["number-merge"]);
    expect(matchesCatalogTopic(project("很经典的新世界", "休闲"), "classic")).toBe(false);
  });

  it("distinguishes snake ordering from classic snake gameplay", () => {
    const ordering = project("蛇蛇出洞", "按顺序放走彩色小蛇，避开阻挡，在倒计时结束前清空棋盘。", "snake-escape");
    expect(matchesCatalogTopic(ordering, "classic")).toBe(false);
    expect(matchesCatalogTopic(ordering, "quick")).toBe(true);
    expect(matchesCatalogTopic(project("反向贪吃蛇 3D"), "classic")).toBe(true);
  });

  it("normalises full-width titles and avoids numbers that only contain 2048", () => {
    expect(matchesCatalogTopic(project("Ａｓｔｒａ ２０４８"), "number-merging")).toBe(true);
    expect(matchesCatalogTopic(project("Project 120480"), "number-merging")).toBe(false);
  });

  it("keeps the small explicit canonical mapping exact", () => {
    expect(matchesCatalogTopic(project("流心西瓜", "休闲", "liuxin-watermelon"), "number-merging")).toBe(true);
    expect(matchesCatalogTopic(project("未注明玩法", null, "liuxin-watermelon-other"), "number-merging")).toBe(false);
  });

  it("keeps real zero-result topics empty instead of falling back to all games", () => {
    const projects = [project("未注明玩法")];
    const counts = countCatalogTopics(projects);
    expect(counts.all).toBe(1);
    for (const topic of CATALOG_MORE_TOPICS) {
      expect(counts[topic.id]).toBe(0);
      expect(projects.filter((entry) => matchesCatalogTopic(entry, topic.id))).toEqual([]);
    }
  });

  it("counts each API project once and does not mutate metadata", () => {
    const entry = Object.freeze(project("Astra 2048", "滑动合并相同数字并挑战 2048。"));
    const projects = Object.freeze([entry]);
    const before = JSON.stringify(projects);
    expect(countCatalogTopics(projects)["number-merging"]).toBe(1);
    expect(JSON.stringify(projects)).toBe(before);
    expect(CATALOG_MORE_TOPICS.map((topic) => topic.name)).toEqual(["数字与合成", "消除与解压", "一指挑战", "棋盘对弈"]);
  });

  it("parses topic URLs independently from source-author and sorting filters", () => {
    expect(parseCatalogNavigation({ topic: "classic" })).toMatchObject({ topic: "classic", author: null, sort: "latest", feed: "discovery" });
    expect(parseCatalogNavigation({ topic: "board-duels", q: "Chess" })).toMatchObject({ topic: "board-duels", search: "Chess" });
    expect(parseCatalogNavigation({ author: "original" }).topic).toBe("all");
    expect(parseCatalogNavigation({ topic: "unknown" }).topic).toBe("all");
    expect(parseCatalogNavigation({ topic: ["classic", "quick"] }).topic).toBe("all");
    expect(isCatalogTopicId("original")).toBe(false);
  });
});
