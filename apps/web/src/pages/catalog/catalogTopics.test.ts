import { describe, expect, it } from "vitest";

import { parseCatalogHeroTopic, parseCatalogNavigation } from "./catalogNavigation";
import { CATALOG_HERO_TABS, matchesCatalogTopic, selectCatalogRecommendations } from "./catalogTopics";

function rated(slug: string, score: number | null) {
  return { slug, aiRating: { score } };
}

describe("catalog hero recommendations", () => {
  it("keeps the four approved hero tabs in their exact order", () => {
    expect(CATALOG_HERO_TABS.map(({ id, name }) => ({ id, name }))).toEqual([
      { id: "all", name: "全部推荐" },
      { id: "nostalgia", name: "经典怀旧" },
      { id: "quick", name: "即玩即乐" },
      { id: "brain", name: "多动脑子" },
    ]);
  });

  it("ranks real scores descending with stable ties without mutating the input", () => {
    const projects = [
      rated("unknown-zero", 0),
      rated("unknown-highest", 10),
      rated("unknown-first-tie", 8),
      rated("unknown-middle", 5),
      rated("unknown-second-tie", 8),
    ];
    const originalOrder = [...projects];
    for (const entry of projects) {
      Object.freeze(entry.aiRating);
      Object.freeze(entry);
    }
    Object.freeze(projects);

    const selected = selectCatalogRecommendations(projects, "all");

    expect(selected.map((entry) => entry.slug)).toEqual([
      "unknown-highest", "unknown-first-tie", "unknown-second-tie", "unknown-middle", "unknown-zero",
    ]);
    expect(selected).not.toBe(projects);
    expect(selected[0]).toBe(projects[1]);
    expect(projects).toEqual(originalOrder);
  });

  it("keeps unknown scores stable after real zero without fabricating scores", () => {
    const projects = [
      { slug: "no-rating" },
      { slug: "null-rating", aiRating: null },
      { slug: "user-rating-only", averageScore: 10, score: 10 },
      rated("null-score", null),
      rated("nan-score", Number.NaN),
      rated("positive-infinity", Number.POSITIVE_INFINITY),
      rated("negative-infinity", Number.NEGATIVE_INFINITY),
      rated("below-zero", -0.01),
      rated("above-ten", 10.01),
      rated("valid-zero", 0),
      rated("valid-ten", 10),
    ];

    const originalOrder = [...projects];
    for (const entry of projects) {
      if (entry.aiRating) Object.freeze(entry.aiRating);
      Object.freeze(entry);
    }
    Object.freeze(projects);

    const selected = selectCatalogRecommendations(projects, "all");

    expect(selected.map((entry) => entry.slug)).toEqual([
      "valid-ten", "valid-zero",
      "no-rating", "null-rating", "user-rating-only", "null-score", "nan-score",
      "positive-infinity", "negative-infinity", "below-zero", "above-ten",
    ]);
    expect(selected[2]).toBe(projects[0]);
    expect(selected.find((entry) => entry.slug === "no-rating")).not.toHaveProperty("aiRating");
    expect(selected.find((entry) => entry.slug === "null-rating")?.aiRating).toBeNull();
    expect(selected.find((entry) => entry.slug === "null-score")?.aiRating?.score).toBeNull();
    expect(selected.find((entry) => entry.slug === "nan-score")?.aiRating?.score).toBeNaN();
    expect(selected.find((entry) => entry.slug === "below-zero")?.aiRating?.score).toBe(-0.01);
    expect(selected.find((entry) => entry.slug === "above-ten")?.aiRating?.score).toBe(10.01);
    expect(projects).toEqual(originalOrder);
    expect(selectCatalogRecommendations([], "all")).toEqual([]);
  });

  it("does not infer a mechanism for an unknown slug from title, metadata or score", () => {
    const unknown = {
      ...rated("unknown-evidence-free-slug", 10),
      name: "2048 Chess Word Puzzle RPG",
      description: "经典怀旧、即玩即乐和多动脑子",
      authorName: "original",
      kind: "internal",
      viewCount: 999999,
    };

    expect(matchesCatalogTopic(unknown, "all")).toBe(true);
    const unscored = { slug: "unknown-unscored", aiRating: null };
    expect(selectCatalogRecommendations([unscored, unknown], "all")).toEqual([unknown, unscored]);
    for (const topic of CATALOG_HERO_TABS) {
      if (topic.id === "all") continue;
      expect(matchesCatalogTopic(unknown, topic.id)).toBe(false);
      expect(selectCatalogRecommendations([unknown], topic.id)).toEqual([]);
      expect(matchesCatalogTopic(unscored, topic.id)).toBe(false);
    }
  });

  it("parses the hero topic independently from every global catalog filter", () => {
    const globalQuery = {
      q: "Chess",
      category: "shooting",
      author: "original",
      sort: "hot",
      feed: "hot",
      scope: "wanted",
      view: "authors",
    };
    const combinedQuery = { ...globalQuery, topic: "nostalgia" };

    expect(parseCatalogHeroTopic(combinedQuery)).toBe("nostalgia");
    expect(parseCatalogNavigation(combinedQuery)).toEqual(parseCatalogNavigation(globalQuery));
    expect(parseCatalogNavigation(combinedQuery)).not.toHaveProperty("topic");
    expect(parseCatalogNavigation(combinedQuery)).not.toHaveProperty("heroTopic");
    expect(parseCatalogNavigation(combinedQuery)).toMatchObject({
      search: "Chess", category: "shooting", author: "original", sort: "hot", feed: "hot", scope: "wanted", view: "authors",
    });
    expect(parseCatalogHeroTopic({ q: "nostalgia", category: "brain", author: "quick" })).toBe("all");
  });

  it("keeps user-confirmed Mario and CS nostalgia separate from ordinary number puzzles", () => {
    expect(matchesCatalogTopic({ slug: "super-mario" }, "nostalgia")).toBe(true);
    expect(matchesCatalogTopic({ slug: "csgo-desert" }, "nostalgia")).toBe(true);
    expect(matchesCatalogTopic({ slug: "astra-2048-eddy" }, "nostalgia")).toBe(false);
    expect(matchesCatalogTopic({ slug: "astra-2048-eddy" }, "brain")).toBe(true);
    expect(matchesCatalogTopic({ slug: "entropy-blade", aiRating: { score: 7.5 } }, "nostalgia")).toBe(false);
  });

  it("accepts only the new hero topic IDs and treats malformed or legacy queries as all", () => {
    for (const topic of CATALOG_HERO_TABS) {
      expect(parseCatalogHeroTopic({ topic: topic.id })).toBe(topic.id);
    }
    for (const topic of ["classic", "word-puzzle", "short-session", "deep-progress", "board-duels", "unknown", "", "NOSTALGIA"]) {
      expect(parseCatalogHeroTopic({ topic })).toBe("all");
    }
    expect(parseCatalogHeroTopic({})).toBe("all");
    expect(parseCatalogHeroTopic({ topic: null })).toBe("all");
    expect(parseCatalogHeroTopic({ topic: ["nostalgia", "quick"] })).toBe("all");
    expect(parseCatalogHeroTopic({ topic: ["brain"] })).toBe("all");
  });
});
