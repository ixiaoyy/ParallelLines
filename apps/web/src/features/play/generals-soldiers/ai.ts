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
  bounds: Map<string, { score: number; bound: "exact" | "lower" | "upper" }>;
  generalDefense: boolean;
  provenLosingRootMoves: Set<string>;
  preferredMoves: Map<string, Move>;
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

function evaluate(state: GameState, generalDefense: boolean): number {
  if (state.winner === "general") return WIN_SCORE - state.ply;
  if (state.winner === "soldier") return -WIN_SCORE + state.ply;

  const generalMoves = legalMoves(state, "general");
  const captures = generalMoves.filter((move) => move.capture).length;
  const soldierOptions = legalMoves(state, "soldier");
  const soldierMoves = soldierOptions.length;

  // 兵方下一手能封住所有将军时提前认出必败，不让搜索深度边界漏掉最后一手。
  if (generalDefense && state.turn === "soldier") {
    const exits = new Set(generalMoves.filter((move) => !move.capture).map((move) => move.to));
    if (exits.size === 1) {
      const [exit] = exits;
      for (const reply of soldierOptions) {
        // 落兵也会腾空原位；必须按真实规则确认没有给其他将军打开新出口。
        if (reply.to === exit && applyLegalMove(state, reply).winner === "soldier") {
          return -WIN_SCORE + state.ply + 1;
        }
      }
    }
  }
  let confinementPenalty = 0;

  // 仅增强高难度电脑将军：分别评估每位将军的退路，避免总走法掩盖局部围困。
  if (generalDefense) {
    const movesByGeneral = new Map<number, number>();
    for (const move of generalMoves) {
      movesByGeneral.set(move.from, (movesByGeneral.get(move.from) ?? 0) + 1);
    }
    for (let index = 0; index < state.board.length; index += 1) {
      if (state.board[index] !== "general") continue;
      const exits = movesByGeneral.get(index) ?? 0;
      confinementPenalty += exits === 0 ? 700 : exits === 1 ? 100 : 0;
    }
  }

  // 将军追求减员与保留退路；小兵追求封锁跳吃路线和活动空间。
  return (
    (15 - state.soldiers) * 420 +
    generalMoves.length * 18 +
    captures * 62 -
    soldierMoves * 3 -
    confinementPenalty
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
  if (depth === 0 || state.winner) return evaluate(state, context.generalDefense);

  const position = positionKey(state);
  // 自动跳过兵方会额外推进手数；增强搜索的缓存包含手数，保留终局快慢评分。
  const cacheKey = context.generalDefense ? `${depth}:${state.ply}:${position}` : `${depth}:${position}`;
  if (context.generalDefense) {
    const cached = context.bounds.get(cacheKey);
    // 精确分数直接复用；上下界只在足以剪枝时返回，不缩窄当前搜索窗口。
    if (cached && (cached.bound === "exact" ||
      cached.bound === "lower" && cached.score >= beta ||
      cached.bound === "upper" && cached.score <= alpha)) return cached.score;
  } else {
    const cached = context.table.get(cacheKey);
    if (cached !== undefined) return cached;
  }

  const moves = legalMoves(state);
  if (moves.length === 0) return evaluate(state, context.generalDefense);
  const preferred = context.generalDefense ? context.preferredMoves.get(position) : undefined;
  // 增强将军优先复查上一轮好棋，其余按吃子优先搜索，在相同预算内尽早剪枝。
  moves.sort((left, right) =>
    Number(right.from === preferred?.from && right.to === preferred?.to) -
    Number(left.from === preferred?.from && left.to === preferred?.to) ||
    Number(right.capture) - Number(left.capture),
  );

  const maximizing = state.turn === "general";
  const originalAlpha = alpha;
  const originalBeta = beta;
  let best = maximizing ? -Infinity : Infinity;
  let bestMove: Move | undefined;
  let cutOff = false;
  for (const move of moves) {
    const value = search(applyLegalMove(state, move), depth - 1, alpha, beta, context);
    if (maximizing ? value > best : value < best) {
      best = value;
      bestMove = move;
    }
    if (maximizing) alpha = Math.max(alpha, best);
    else beta = Math.min(beta, best);
    if (beta <= alpha) {
      cutOff = true;
      break;
    }
  }
  // 增强搜索按原始窗口保存边界类型；其他阵营和难度保留原缓存方式。
  if (context.generalDefense) {
    const bound = best <= originalAlpha ? "upper" : best >= originalBeta ? "lower" : "exact";
    context.bounds.set(cacheKey, { score: best, bound });
  } else if (!cutOff) {
    context.table.set(cacheKey, best);
  }
  if (context.generalDefense && bestMove) context.preferredMoves.set(position, bestMove);
  return best;
}

function rankMoves(
  state: GameState,
  depth: number,
  context: SearchContext,
  recentPositions: Set<string>,
): ScoredMove[] {
  const side = state.turn;
  const moves = legalMoves(state);
  const moveOrder = new Map(moves.map((move, index) => [move, index]));
  const position = positionKey(state);
  let rootAlpha = -Infinity;
  // 增强将军没有随机次优选择；先搜索上一层最佳候选，再共享根节点下界。
  if (context.generalDefense) {
    const preferred = context.preferredMoves.get(position);
    moves.sort((left, right) =>
      Number(right.from === preferred?.from && right.to === preferred?.to) -
      Number(left.from === preferred?.from && left.to === preferred?.to),
    );
  }
  const scored = moves.map((move) => {
    const next = applyLegalMove(state, move);
    // 只影响电脑偏好，不把重复局面判为和局。
    const repetition = recentPositions.has(positionKey(next)) && !next.winner
      ? side === "general" ? -34 : 34
      : 0;
    // 评分均为整数；窗口多留一分，让同分候选算出精确值并保留原来的走法顺序。
    const alpha = context.generalDefense ? rootAlpha - repetition - 1 : -Infinity;
    const rawScore = search(next, depth - 1, alpha, Infinity, context);
    // 只保留完整候选返回的必败证明；后续候选超预算时也不能重新选回这手棋。
    if (context.generalDefense && rawScore < -WIN_SCORE / 2) {
      context.provenLosingRootMoves.add(`${move.from}:${move.to}`);
    }
    const score = rawScore + repetition;
    if (context.generalDefense) rootAlpha = Math.max(rootAlpha, score);
    return { move, score };
  });
  scored.sort((left, right) =>
    (side === "general" ? right.score - left.score : left.score - right.score) ||
    moveOrder.get(left.move)! - moveOrder.get(right.move)!,
  );
  if (context.generalDefense && scored[0]) context.preferredMoves.set(position, scored[0].move);
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
    bounds: new Map(),
    // 按电脑执棋方确定整次搜索策略，不影响电脑小兵及简单、普通难度。
    generalDefense: state.turn === "general" && (difficulty === "hard" || difficulty === "hell"),
    preferredMoves: new Map(),
    provenLosingRootMoves: new Set(),
  };
  const recent = new Set(recentPositions);
  let ranked: ScoredMove[] = [{ move: moves[0]!, score: 0 }];
  let completedDepth = 0;

  // 高难度将军在原时间和节点预算内继续加深；小兵和低难度仍用原深度上限。
  const maxDepth = context.generalDefense ? difficulty === "hell" ? 11 : 9 : profile.maxDepth;
  for (let depth = 1; depth <= maxDepth; depth += 1) {
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

  // 普通评分仍取同一完整层，只排除已证败走法；全都已证败时保留原来的合法选择。
  if (context.generalDefense) {
    const remaining = ranked.filter(({ move }) => !context.provenLosingRootMoves.has(`${move.from}:${move.to}`));
    if (remaining.length > 0) ranked = remaining;
  }

  return {
    move: chooseFromRanked(ranked, state.turn, profile, random),
    depth: completedDepth,
    nodes: context.nodes,
  };
}
