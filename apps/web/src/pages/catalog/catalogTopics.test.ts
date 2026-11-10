import { describe, expect, it } from "vitest";

import { parseCatalogHeroTopic, parseCatalogNavigation } from "./catalogNavigation";
import { CATALOG_HERO_TABS, catalogRecommendationSlugs, matchesCatalogTopic, selectCatalogRecommendations } from "./catalogTopics";

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
      rated("dragonsweeper", 0),
      rated("growmi", 10),
      rated("sort-the-court", 8),
      rated("solitomb", 5),
      rated("slipways-classic", 8),
    ];
    const originalOrder = [...projects];
    for (const entry of projects) {
      Object.freeze(entry.aiRating);
      Object.freeze(entry);
    }
    Object.freeze(projects);

    const selected = selectCatalogRecommendations(projects, "all");

    expect(selected.map((entry) => entry.slug)).toEqual([
      "growmi", "sort-the-court", "slipways-classic", "solitomb", "dragonsweeper",
    ]);
    expect(selected).not.toBe(projects);
    expect(selected[0]).toBe(projects[1]);
    expect(projects).toEqual(originalOrder);
  });

  it.each([
    { label: "absent rating", rating: {} },
    { label: "null rating", rating: { aiRating: null } },
    { label: "player rating only", rating: { averageScore: 10, score: 10 } },
    { label: "null score", rating: { aiRating: { score: null } } },
    { label: "NaN", rating: { aiRating: { score: Number.NaN } } },
    { label: "positive infinity", rating: { aiRating: { score: Number.POSITIVE_INFINITY } } },
    { label: "negative infinity", rating: { aiRating: { score: Number.NEGATIVE_INFINITY } } },
    { label: "below zero", rating: { aiRating: { score: -0.01 } } },
    { label: "above ten", rating: { aiRating: { score: 10.01 } } },
  ])("keeps $label unknown after real zero without fabricating scores", ({ rating }) => {
    const unknown = { slug: "dragonsweeper", ...rating };
    const projects = [
      unknown,
      { slug: "die-in-the-dungeon-classic" },
      rated("growmi", 0),
      rated("solitomb", 10),
    ];

    const originalOrder = [...projects];
    for (const entry of projects) {
      if (entry.aiRating) Object.freeze(entry.aiRating);
      Object.freeze(entry);
    }
    Object.freeze(projects);

    const selected = selectCatalogRecommendations(projects, "all");

    expect(selected.map((entry) => entry.slug)).toEqual([
      "solitomb", "growmi", "dragonsweeper", "die-in-the-dungeon-classic",
    ]);
    expect(selected[2]).toBe(unknown);
    expect(selected[2]).toEqual({ slug: "dragonsweeper", ...rating });
    expect(selected[3]).not.toHaveProperty("aiRating");
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

    expect(matchesCatalogTopic(unknown, "all")).toBe(false);
    const unscored = { slug: "unknown-unscored", aiRating: null };
    expect(selectCatalogRecommendations([unscored, unknown], "all")).toEqual([]);
    for (const topic of CATALOG_HERO_TABS) {
      if (topic.id === "all") continue;
      expect(matchesCatalogTopic(unknown, topic.id)).toBe(false);
      expect(selectCatalogRecommendations([unknown], topic.id)).toEqual([]);
      expect(matchesCatalogTopic(unscored, topic.id)).toBe(false);
    }
  });

  it("uses exactly the approved editorial pool for all without altering the source catalog", () => {
    const slugs = ["dragonsweeper", "growmi", "sort-the-court", "solitomb", "slipways-classic", "die-in-the-dungeon-classic"];
    expect(catalogRecommendationSlugs("all")).toEqual(slugs);
    const old = rated("astra-d29e74ac15e222629347", 10);
    const current = slugs.map((slug) => ({ slug, aiRating: null }));
    const catalog = [old, ...current];
    expect(selectCatalogRecommendations(catalog, "all")).toEqual(current);
    expect(catalog).toEqual([old, ...current]);
    for (const project of current) {
      expect(matchesCatalogTopic(project, "all")).toBe(true);
      expect(matchesCatalogTopic(project, "nostalgia")).toBe(false);
      expect(matchesCatalogTopic(project, "quick")).toBe(false);
      expect(matchesCatalogTopic(project, "brain")).toBe(false);
    }
  });

  it("keeps missing editorial members absent rather than filling from older scored games", () => {
    const old = rated("astra-d29e74ac15e222629347", 10);
    const available = { slug: "growmi", aiRating: null };
    expect(selectCatalogRecommendations([old, available], "all")).toEqual([available]);
    expect(selectCatalogRecommendations([old], "all")).toEqual([]);
  });

  it("shares each topic candidate list with full-catalog selection and keeps other topics independent", () => {
    for (const tab of CATALOG_HERO_TABS) {
      const candidates = catalogRecommendationSlugs(tab.id);
      expect(new Set(candidates).size).toBe(candidates.length);
      for (const slug of candidates) expect(matchesCatalogTopic({ slug }, tab.id)).toBe(true);
      expect(selectCatalogRecommendations(candidates.map((slug) => ({ slug })), tab.id).map((entry) => entry.slug))
        .toEqual(candidates);
    }
    expect(catalogRecommendationSlugs("nostalgia")).toEqual([
      "astra-9dbd59a9718b252daedf", "astra-2a8764b03af3aca71817", "super-mario", "csgo-desert",
    ]);
    const old = rated("astra-2048-eddy", 8);
    expect(selectCatalogRecommendations([old], "quick")).toEqual([old]);
    expect(selectCatalogRecommendations([old], "brain")).toEqual([old]);
    expect(selectCatalogRecommendations([old], "all")).toEqual([]);
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
