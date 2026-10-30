/** Hero-only topics. Live records, covers and ratings always come from the API. */
export const CATALOG_HERO_TABS = [
  { id: "all", name: "全部推荐" },
  { id: "nostalgia", name: "经典怀旧" },
  { id: "quick", name: "即玩即乐" },
  { id: "brain", name: "多动脑子" },
] as const;

export type CatalogTopicId = typeof CATALOG_HERO_TABS[number]["id"];
type MechanicTopic = Exclude<CatalogTopicId, "all">;

export interface CatalogTopicProject {
  readonly slug: string;
  readonly aiRating?: { readonly score: number | null } | null;
}

interface RecommendationEvidence {
  readonly topics: readonly MechanicTopic[];
  readonly source: "api.description" | "accepted_external_review" | "user_confirmed_identity";
  readonly mechanics: string;
}

/**
 * Curated mechanic metadata, not a game list: resolve exact identifiers against
 * live API records, so missing or hidden games never enter recommendations.
 * The accepted external reviews and explicit API descriptions support these
 * mechanics. A short session is not a promise of five-minute completion.
 * Titles, authors, broad categories and scores do not imply a topic.
 */
export const CATALOG_RECOMMENDATION_EVIDENCE: Readonly<Record<string, RecommendationEvidence>> = {
  "astra-9dbd59a9718b252daedf": { topics: ["nostalgia"], source: "api.description", mechanics: "Mario Mix II: Ninja Gaiden/Battle City characters in Mario underground stage 1-2; explicit old-game crossover homage." },
  "astra-2a8764b03af3aca71817": { topics: ["nostalgia"], source: "api.description", mechanics: "Explicit unofficial Mario platformer and Duck Hunt cartridge-game port." },
  "super-mario": { topics: ["nostalgia"], source: "user_confirmed_identity", mechanics: "User explicitly identified Mario as nostalgic; API official name Super Mario. Description is null; no version or restoration claim." },
  "csgo-desert": { topics: ["nostalgia"], source: "user_confirmed_identity", mechanics: "User explicitly identified CS as nostalgic; API CSGO Desert Action with Dust II URL. Description is null; original-game fidelity is unverified." },
  "astra-9901d0cd25f74f721cf1": { topics: ["brain"], source: "accepted_external_review", mechanics: "Compare present/echo clues, solve ordering and 2/4/6 signal constraints; two puzzles reported solved." },
  "astra-7e0d2e37b2e9a32fdd31": { topics: ["brain", "quick"], source: "accepted_external_review", mechanics: "Six-piece interlocking wood puzzle and sliding blocks; first lock completed in 01:23, not the whole game." },
  "astra-2048-eddy": { topics: ["brain", "quick"], source: "api.description", mechanics: "Discrete directional moves merge equal numbers towards 2048." },
  "astra-940973d6b1805a52c1f0": { topics: ["brain"], source: "api.description", mechanics: "Mystery Town: inspect and manipulate objects, solve environmental puzzles in causal order." },
  "astra-27f541f14365c72d05f5": { topics: ["brain"], source: "api.description", mechanics: "Greenhouse Escape Room: repair copper pipes, position plants and reflect light to solve puzzles." },
  "astra-6db391ac7ca0252ae0e0": { topics: ["brain"], source: "api.description", mechanics: "Pixel Orchard: remember twelve seed cards and find six matching pairs, with move counting and shuffling." },
  "astra-a146ecd81e3c0fd17f7c": { topics: ["brain"], source: "api.description", mechanics: "Chess Cubed: plan chess moves and threats over six connected cube faces using rotation and a flat view." },
  "snake-escape": { topics: ["brain"], source: "api.description", mechanics: "Release colored snakes in a valid order, avoid blockers and clear the board before the countdown." },
  "astra-e48428f88519b6c8b7a3": { topics: ["quick"], source: "accepted_external_review", mechanics: "APEX CLUB: bounded three-lap races; no whole-race time claim." },
  "pelican-rider": { topics: ["quick"], source: "api.description", mechanics: "A race to a finish line with stamina, obstacles and items; bounded-round inference, duration unmeasured." },
  "astra-427abefc3be5bb52b0f4": { topics: ["quick"], source: "accepted_external_review", mechanics: "An independent three-wave fight; report reached wave 2/3 around 21 seconds." },
  "astra-169a094a99f2babbad62": { topics: ["quick"], source: "accepted_external_review", mechanics: "TIDAL RUSH: bounded three-lap, eight-racer contest; no measured completion duration." },
  "astra-c3ad2159872d2b53299e": { topics: ["quick"], source: "accepted_external_review", mechanics: "Three-lap solo race actually entered; no whole-race duration claim." },
};

export function isCatalogTopicId(value: string): value is CatalogTopicId {
  return CATALOG_HERO_TABS.some((tab) => tab.id === value);
}

export function matchesCatalogTopic(project: CatalogTopicProject, topic: CatalogTopicId): boolean {
  if (topic === "all") return true;
  if (!Object.prototype.hasOwnProperty.call(CATALOG_RECOMMENDATION_EVIDENCE, project.slug)) return false;
  return CATALOG_RECOMMENDATION_EVIDENCE[project.slug].topics.includes(topic);
}

function recommendationScore(project: CatalogTopicProject): number | null {
  const score = project.aiRating?.score;
  return typeof score === "number" && Number.isFinite(score) && score >= 0 && score <= 10 ? score : null;
}

/** Valid scores first, descending; unknown stays unknown. Stable ties preserve API order. */
export function selectCatalogRecommendations<T extends CatalogTopicProject>(projects: readonly T[], topic: CatalogTopicId): T[] {
  return projects.filter((project) => matchesCatalogTopic(project, topic)).map((project, index) => ({
    project, index, score: recommendationScore(project),
  })).sort((left, right) => {
    if (left.score === null) return right.score === null ? left.index - right.index : 1;
    if (right.score === null) return -1;
    return right.score - left.score || left.index - right.index;
  }).map(({ project }) => project);
}
