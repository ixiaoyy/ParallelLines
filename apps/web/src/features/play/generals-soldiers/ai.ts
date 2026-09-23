import {
  applyLegalMove,
  legalMoves,
  positionKey,
  type GameState,
  type Move,
  type Side,
} from "./rules";

export type Difficulty = "easy" | "normal" | "hard" | "hell";

export interface AiRequest {
  id: number;
  state: GameState;
  difficulty: Difficulty;
  recentPositions: string[];
}

export interface AiResponse {
  id: number;
  move: Move | null;
  depth: number;
  nodes: number;
}

interface Profile {
  maxDepth: number;
  timeMs: number;
  nodeLimit: number;
  candidateWindow: number;
  alternativeChance: number;
}

interface SearchContext {
  deadline: number;
  nodeLimit: number;
  nodes: number;
  table: Map<string, number>;
}

interface ScoredMove {
  move: Move;
  score: number;
}

const WIN_SCORE = 1_000_000;
const PROFILES: Record<Difficulty, Profile> = {
  easy: { maxDepth: 1, timeMs: 90, nodeLimit: 1_200, candidateWindow: 260, alternativeChance: 0.48 },
  normal: { maxDepth: 2, timeMs: 220, nodeLimit: 8_000, candidateWindow: 75, alternativeChance: 0.12 },
  hard: { maxDepth: 4, timeMs: 700, nodeLimit: 45_000, candidateWindow: 0, alternativeChance: 0 },
  hell: { maxDepth: 7, timeMs: 1_500, nodeLimit: 160_000, candidateWindow: 0, alternativeChance: 0 },
};

class SearchInterrupted extends Error {}

function evaluate(state: GameState): number {
  if (state.winner === "general") return WIN_SCORE - state.ply;
  if (state.winner === "soldier") return -WIN_SCORE + state.ply;

  const generalMoves = legalMoves(state, "general");
  const captures = generalMoves.filter((move) => move.capture).length;
  const soldierMoves = legalMoves(state, "soldier").length;

  // 将军追求减员与保留退路；小兵追求封锁跳吃路线和活动空间。
  return (
    (15 - state.soldiers) * 420 +
    generalMoves.length * 18 +
    captures * 62 -
    soldierMoves * 3
  );
}

function checkLimit(context: SearchContext): void {
  context.nodes += 1;
  if (context.nodes > context.nodeLimit || (context.nodes & 255) === 0 && performance.now() >= context.deadline) {
    throw new SearchInterrupted();
  }
}

function search(state: GameState, depth: number, alpha: number, beta: number, context: SearchContext): number {
  checkLimit(context);
  if (depth === 0 || state.winner) return evaluate(state);

  const cacheKey = `${depth}:${positionKey(state)}`;
  const cached = context.table.get(cacheKey);
  if (cached !== undefined) return cached;

  const moves = legalMoves(state);
  if (moves.length === 0) return evaluate(state);
  // 吃子先搜索，更容易提前发现将军胜利并剪掉无关分支。
  moves.sort((left, right) => Number(right.capture) - Number(left.capture));

  const maximizing = state.turn === "general";
  let best = maximizing ? -Infinity : Infinity;
  let cutOff = false;
  for (const move of moves) {
    const value = search(applyLegalMove(state, move), depth - 1, alpha, beta, context);
    best = maximizing ? Math.max(best, value) : Math.min(best, value);
    if (maximizing) alpha = Math.max(alpha, best);
    else beta = Math.min(beta, best);
    if (beta <= alpha) {
      cutOff = true;
      break;
    }
  }
  // 剪枝后的值只是边界；仅缓存完整搜索的局面，避免误导后续走法。
  if (!cutOff) context.table.set(cacheKey, best);
  return best;
}

function rankMoves(
  state: GameState,
  depth: number,
  context: SearchContext,
  recentPositions: Set<string>,
): ScoredMove[] {
  const side = state.turn;
  const scored = legalMoves(state).map((move) => {
    const next = applyLegalMove(state, move);
    let score = search(next, depth - 1, -Infinity, Infinity, context);
    // 只影响电脑偏好，不把重复局面判为和局。
    if (recentPositions.has(positionKey(next)) && !next.winner) {
      score += side === "general" ? -34 : 34;
    }
    return { move, score };
  });
  scored.sort((left, right) => side === "general" ? right.score - left.score : left.score - right.score);
  return scored;
}

function chooseFromRanked(ranked: ScoredMove[], side: Side, profile: Profile, random: () => number): Move {
  const best = ranked[0];
  if (!best) throw new Error("AI has no legal move");
  if (profile.alternativeChance === 0 || random() >= profile.alternativeChance) return best.move;

  const bestForSide = side === "general" ? best.score : -best.score;
  // 低难度只从分数接近的候选中失误，遇到立即获胜仍会选胜着。
  const alternatives = ranked.slice(1, 4).filter((item) => {
    const scoreForSide = side === "general" ? item.score : -item.score;
    return bestForSide - scoreForSide <= profile.candidateWindow;
  });
  return alternatives.length > 0
    ? alternatives[Math.floor(random() * alternatives.length)]?.move ?? best.move
    : best.move;
}

/** 在限定时间和节点数内迭代搜索，返回最近一次完整搜索的合法走法。 */
export function chooseAiMove(
  state: GameState,
  difficulty: Difficulty,
  recentPositions: string[] = [],
  random: () => number = Math.random,
): Omit<AiResponse, "id"> {
  const moves = legalMoves(state);
  if (moves.length === 0) return { move: null, depth: 0, nodes: 0 };

  const profile = PROFILES[difficulty];
  const context: SearchContext = {
    deadline: performance.now() + profile.timeMs,
    nodeLimit: profile.nodeLimit,
    nodes: 0,
    table: new Map(),
  };
  const recent = new Set(recentPositions);
  let ranked: ScoredMove[] = [{ move: moves[0]!, score: 0 }];
  let completedDepth = 0;

  for (let depth = 1; depth <= profile.maxDepth; depth += 1) {
    try {
      const fullRanking = rankMoves(state, depth, context, recent);
      ranked = fullRanking;
      completedDepth = depth;
      if (Math.abs(fullRanking[0]?.score ?? 0) > WIN_SCORE / 2) break;
    } catch (error) {
      if (!(error instanceof SearchInterrupted)) throw error;
      break;
    }
  }

  return {
    move: chooseFromRanked(ranked, state.turn, profile, random),
    depth: completedDepth,
    nodes: context.nodes,
  };
}
