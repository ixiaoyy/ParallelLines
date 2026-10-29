/** Read-only gameplay topics. These rules select existing API projects; they create no games or categories. */
export interface CatalogTopicProject {
  readonly slug: string;
  readonly name: string;
  readonly description: string | null;
}

type GameplayId = "number-merge" | "watermelon-merge" | "match" | "tetris" | "minesweeper"
  | "sudoku" | "sokoban" | "chess" | "go" | "property-board" | "mario"
  | "asteroids" | "snake" | "fruit-slicing" | "flappy" | "bubble-wrap" | "classic-handheld"
  | "snake-ordering";

interface GameplayRule {
  readonly id: GameplayId;
  readonly label: string;
  readonly name?: RegExp;
  readonly slug?: RegExp;
  readonly description?: RegExp;
}

/**
 * Name/description rules require a recognisable gameplay identity, not an author,
 * popularity score, AI score or a broad category. A slug rule is an explicit
 * maintained identity mapping for an existing catalog identifier, never a card list.
 * Missing metadata is deliberately not guessed. Play duration is not inferred.
 */
export const CATALOG_GAMEPLAY_RULES: readonly GameplayRule[] = [
  { id: "number-merge", label: "2048 数字合并", name: /(?:^|\D)2048(?:\D|$)/i, description: /(?:^|\D)2048(?:\D|$)/i },
  { id: "watermelon-merge", label: "水果合成", name: /合成.*(?:西瓜|水果)|(?:西瓜|水果).*合成/, slug: /^(?:merge-watermelon|liuxin-watermelon)$/ },
  { id: "match", label: "连色消除", name: /消消乐|三消|连连看|\bmatch[ -]?3\b/i, description: /点击消除至少三颗相连的同色泡泡/ },
  { id: "tetris", label: "俄罗斯方块", name: /俄罗斯方块|\btetris\b/i, description: /俄罗斯方块|\btetris\b/i },
  { id: "minesweeper", label: "扫雷", name: /扫雷|\bminesweeper\b/i },
  { id: "sudoku", label: "数独", name: /数独|\bsudoku\b/i },
  { id: "sokoban", label: "推箱子", name: /推箱子|\bsokoban\b/i },
  { id: "chess", label: "国际象棋", name: /国际象棋|西洋棋|\bchess\b/i, description: /国际象棋|西洋棋/ },
  { id: "go", label: "围棋", name: /围棋/, description: /对弈围棋|围棋对弈/ },
  { id: "property-board", label: "地产棋盘对局", name: /大富翁|\bmonopoly\b/i },
  { id: "mario", label: "马里奥平台闯关", name: /马里奥|超级玛丽|\bmario\b/i },
  { id: "asteroids", label: "小行星惯性射击", name: /\basteroids\b/i },
  { id: "snake", label: "贪吃蛇", name: /贪吃蛇|^(?:reverse[ -])?snake(?:[ -]3d)?$/i },
  { id: "fruit-slicing", label: "切水果", name: /水果忍者|\bfruit[ -]?ninja\b/i },
  { id: "flappy", label: "点按穿障", name: /\bflappy[ -]?(?:bird|dunk)\b|\bmiami[ -]flap\b/i, slug: /^(?:flappy-dunk|miami-flap)$/ },
  { id: "bubble-wrap", label: "戳泡泡解压", name: /\bbubble[ -]wrap\b|捏泡泡|戳泡泡/i },
  { id: "classic-handheld", label: "经典掌机玩法合集", description: /贪吃蛇.*(?:扫雷|推箱子)/ },
  { id: "snake-ordering", label: "顺序放行小蛇", description: /按顺序放走彩色小蛇/ },
];

const classic: readonly GameplayId[] = ["number-merge", "tetris", "minesweeper", "sudoku", "sokoban", "chess", "go", "property-board", "mario", "asteroids", "snake", "fruit-slicing", "flappy", "classic-handheld"];
const quick: readonly GameplayId[] = ["number-merge", "watermelon-merge", "match", "tetris", "minesweeper", "snake", "fruit-slicing", "flappy", "bubble-wrap", "classic-handheld", "snake-ordering"];

export const CATALOG_TOPICS = [
  { id: "classic", name: "经典游戏", description: "熟悉的棋盘、数字与街机玩法，也有网页复刻和新变体。", gameplay: classic },
  { id: "quick", name: "即玩即乐", description: "合成、消除、点按街机，随手来一局。", gameplay: quick },
  { id: "number-merging", name: "数字与合成", description: "把数字或水果合在一起，试着走得更远。", gameplay: ["number-merge", "watermelon-merge"] },
  { id: "matching-relaxation", name: "消除与解压", description: "连色消除，或轻轻戳破一片泡泡。", gameplay: ["match", "bubble-wrap"] },
  { id: "one-button", name: "一指挑战", description: "点按起落，在空隙之间接续挑战。", gameplay: ["flappy"] },
  { id: "board-duels", name: "棋盘对弈", description: "国际象棋、围棋与地产棋盘的新演绎。", gameplay: ["chess", "go", "property-board"] },
] as const;

export type CatalogTopicId = "all" | typeof CATALOG_TOPICS[number]["id"];
export const CATALOG_MORE_TOPICS = CATALOG_TOPICS.filter((topic) => topic.id !== "classic" && topic.id !== "quick");

export function isCatalogTopicId(value: string): value is CatalogTopicId {
  return value === "all" || CATALOG_TOPICS.some((topic) => topic.id === value);
}

export function catalogTopicFor(id: CatalogTopicId) {
  return CATALOG_TOPICS.find((topic) => topic.id === id);
}

function normalise(value: string | null): string {
  return (value ?? "").normalize("NFKC").trim();
}

/** Explainable matches are also available to audits; source fields are never altered. */
export function catalogGameplayFor(project: CatalogTopicProject): readonly GameplayRule[] {
  const name = normalise(project.name);
  const slug = normalise(project.slug);
  const description = normalise(project.description);
  return CATALOG_GAMEPLAY_RULES.filter((rule) => Boolean(
    rule.name?.test(name) || rule.slug?.test(slug) || rule.description?.test(description),
  ));
}

export function matchesCatalogTopic(project: CatalogTopicProject, id: CatalogTopicId): boolean {
  if (id === "all") return true;
  const topic = catalogTopicFor(id);
  if (!topic) return false;
  const accepted = new Set<GameplayId>(topic.gameplay);
  return catalogGameplayFor(project).some((rule) => accepted.has(rule.id));
}

export function countCatalogTopics(projects: readonly CatalogTopicProject[]): Record<CatalogTopicId, number> {
  const counts = { all: projects.length } as Record<CatalogTopicId, number>;
  for (const topic of CATALOG_TOPICS) counts[topic.id] = projects.filter((project) => matchesCatalogTopic(project, topic.id)).length;
  return counts;
}
