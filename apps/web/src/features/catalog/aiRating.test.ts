import { describe, expect, it } from "vitest";

import { compareAiRating, selectAiRecommendations } from "./aiRating";
import type { CatalogAiRating, CatalogJsonValue, CatalogProject } from "./model";

type Entry = CatalogProject & { categorySlug: string };

function rating(score: number | null, playScope: Record<string, CatalogJsonValue> = {}): CatalogAiRating {
  return {
    score, label: "AI评分", assessmentId: "assessment-1", ruleVersion: "dimensions-v1",
    weightVersion: "weights-v1", sourceKind: "independent_ai", evaluatedAt: null,
    reportedReviewDate: "2026-10-29", reportedTimezone: null, gameVersion: null,
    dimensions: [], playScope, limitations: [],
  };
}

function entry(id: string, score: number | null | undefined, categorySlug = "cards", changes: Partial<Entry> = {}): Entry {
  return {
    id, slug: `fixture-${id}`, name: id, url: "https://example.invalid/game", kind: "external",
    description: null, authorName: null, createdAt: "2026-10-20T00:00:00Z", averageScore: null,
    ratingCount: 0, ratingScoreSum: 0, viewCount: 0, myScore: null, host: "example.invalid",
    categorySlug, aiRating: score === undefined ? undefined : rating(score), ...changes,
  };
}

describe("AI rating order", () => {
  it("sorts scores descending, keeps zero, and puts incomplete/missing scores last", () => {
    const projects = [entry("unknown", undefined), entry("incomplete", null), entry("zero", 0), entry("best", 8.3)];
    expect([...projects].sort(compareAiRating).map((project) => project.id))
      .toEqual(["best", "zero", "unknown", "incomplete"]);
    expect(projects[0].id).toBe("unknown");
  });

  it("keeps stable exact string IDs on ties without lossy number conversion", () => {
    const projects = [entry("9007199254740993", 7), entry("9007199254740992", 7), entry("001", 7)];
    expect(compareAiRating(projects[0], projects[1])).toBe(0);
    expect([...projects].sort(compareAiRating).map((project) => project.id))
      .toEqual(["9007199254740993", "9007199254740992", "001"]);
  });
});

describe("AI recommendations", () => {
  it("uses AI scores without player hearts or popularity and preserves its input", () => {
    const projects = [entry("popular", 4, "cards", { ratingScoreSum: 100_000, viewCount: 1_000_000 }),
      entry("quality", 8, "cards")];
    expect(selectAiRecommendations(projects, 2).map((project) => project.id)).toEqual(["quality", "popular"]);
    expect(projects.map((project) => project.id)).toEqual(["popular", "quality"]);
  });

  it("rotates categories only within equal scores and never boosts a lower score above them", () => {
    const projects = [entry("a1", 8, "cards"), entry("a2", 8, "cards"), entry("b1", 8, "rts"),
      entry("a3", 8, "cards"), entry("c1", 7.9, "arcade")];
    expect(selectAiRecommendations(projects, 5).map((project) => project.id))
      .toEqual(["a1", "b1", "a2", "a3", "c1"]);
  });

  it("keeps unknown device compatibility eligible and never infers it from desktop scope", () => {
    const unknown = entry("unknown", 9, "cards", { aiRating: rating(9, { platform: "desktop" }) });
    const tested = entry("tested", 8, "rts", {
      aiRating: rating(8, { device_checks: { mobile: { tested: true, compatible: true } } }),
    });
    const incompatible = entry("incompatible", 10, "arcade", {
      aiRating: rating(10, { device_checks: { mobile: { tested: true, compatible: false } } }),
    });
    expect(selectAiRecommendations([unknown, tested, incompatible], 3, { isMobile: true })
      .map((project) => project.id)).toEqual(["unknown", "tested"]);
    expect(selectAiRecommendations([unknown, incompatible], 2).map((project) => project.id))
      .toEqual(["incompatible", "unknown"]);
  });

  it("uses a completed compatible-device check to break an otherwise equal tie", () => {
    const projects = [entry("unknown", 8), entry("tested", 8, "cards", {
      aiRating: rating(8, { device_checks: { desktop: { tested: true, compatible: true } } }),
    }), entry("untested", 8, "cards", {
      aiRating: rating(8, { device_checks: { desktop: { tested: false, compatible: false } } }),
    })];
    expect(selectAiRecommendations(projects, 3, { isMobile: false }).map((project) => project.id))
      .toEqual(["tested", "unknown", "untested"]);
  });

  it("uses at most one newest unscored exploration slot when scored games leave room", () => {
    const projects = [entry("rated", 0), entry("old", undefined),
      entry("new", null, "rts", { createdAt: "2026-10-29T00:00:00Z" }), entry("other", undefined)];
    const selected = selectAiRecommendations(projects, 6);
    expect(selected.map((project) => project.id)).toEqual(["rated", "new"]);
    expect(selected[1].aiRating?.score).toBeNull();
    expect(selectAiRecommendations(projects, 1).map((project) => project.id)).toEqual(["rated"]);
  });

  it("keeps the previous recommendation order if no AI scores are available", () => {
    const projects = [entry("old-first", undefined), entry("new-last", null, "rts", {
      createdAt: "2026-10-29T00:00:00Z", ratingScoreSum: 100_000,
    })];
    expect(selectAiRecommendations(projects, 2)).toEqual(projects);
    expect(selectAiRecommendations(projects, 0)).toEqual([]);
  });
});
