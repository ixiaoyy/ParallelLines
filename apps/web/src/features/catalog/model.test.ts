import { describe, expect, it } from "vitest";

import {
  toCatalogAiRating,
  toCatalogCategory,
  type CatalogAiRatingResponse,
  type CatalogProjectResponse,
} from "./model";

function aiResponse(changes: Partial<CatalogAiRatingResponse> = {}): CatalogAiRatingResponse {
  return {
    score: 6.9,
    label: "AI评分",
    assessment_id: "assessment-1",
    rule_version: "visible-complexity-content-v1",
    weight_version: "weights-v1",
    source_kind: "user_accepted_external_ai",
    evaluated_at: "2026-10-29T07:00:00Z",
    reported_review_date: null,
    reported_timezone: null,
    game_version: null,
    dimensions: [{ key: "visual", label: "视觉表现（声音未验证）", score: null, weight: 0.05 }],
    play_scope: { platform: "desktop", tested_audio: false, notes: ["tutorial", null] },
    limitations: ["未验证声音与移动端"],
    ...changes,
  };
}

function projectResponse(changes: Partial<CatalogProjectResponse> = {}): CatalogProjectResponse {
  return {
    id: "9007199254740993", slug: "fixture", name: "Fixture", url: "https://example.invalid/game",
    kind: "external", description: null, author_name: null, author_url: null, icon_url: null,
    created_at: "2026-10-28T00:00:00Z", average_score: 4.5, rating_count: 4,
    rating_score_sum: 18, view_count: 28, my_score: 5, ...changes,
  };
}

describe("catalog AI response mapping", () => {
  it("maps provenance and declared dimensions without relabeling visual as audio", () => {
    const result = toCatalogAiRating(aiResponse());
    expect(result).toMatchObject({
      score: 6.9, label: "AI评分", assessmentId: "assessment-1",
      ruleVersion: "visible-complexity-content-v1", weightVersion: "weights-v1",
      sourceKind: "user_accepted_external_ai", evaluatedAt: "2026-10-29T07:00:00Z",
      reportedReviewDate: null, reportedTimezone: null, gameVersion: null,
      dimensions: [{ key: "visual", label: "视觉表现（声音未验证）", score: null, weight: 0.05 }],
      playScope: { platform: "desktop", tested_audio: false, notes: ["tutorial", null] },
      limitations: ["未验证声音与移动端"],
    });
  });

  it("preserves date-only provenance and incomplete/zero scores without inventing time", () => {
    expect(toCatalogAiRating(aiResponse({
      score: null, evaluated_at: null, reported_review_date: "2026-10-29", reported_timezone: null,
    }))).toMatchObject({
      score: null, evaluatedAt: null, reportedReviewDate: "2026-10-29", reportedTimezone: null,
    });
    expect(toCatalogAiRating(aiResponse({ score: 0 }))?.score).toBe(0);
  });

  it.each([
    undefined, null, {},
    { ...aiResponse(), source_kind: "player" },
    { ...aiResponse(), score: Number.NaN },
    { ...aiResponse(), score: 11 },
    { ...aiResponse(), label: "玩家评价" },
    { ...aiResponse(), evaluated_at: "not-a-date" },
  ])("treats missing or unknown AI response shapes as unavailable", (value) => {
    expect(toCatalogAiRating(value)).toBeNull();
  });

  it("maps optional AI summaries while preserving player ratings and views", () => {
    const result = toCatalogCategory({
      id: "1", slug: "games", name: "Games", icon_url: null,
      projects: [projectResponse(), projectResponse({ id: "2", ai_rating: null }),
        projectResponse({ id: "3", ai_rating: aiResponse() })],
    });
    expect(result.projects.map((project) => project.aiRating?.score ?? null)).toEqual([null, null, 6.9]);
    expect(result.projects[2]).toMatchObject({
      averageScore: 4.5, ratingCount: 4, ratingScoreSum: 18, viewCount: 28, myScore: 5,
    });
    expect(result.projects[0].id).toBe("9007199254740993");
  });
});
