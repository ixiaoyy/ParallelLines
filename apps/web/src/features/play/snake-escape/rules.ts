import levelData from "./levels";

export const LEVEL_COUNT = levelData.length;
export const INITIAL_LIVES = 3;
export const LEVEL_TIME_MS = 5 * 60 * 1_000;
export const INITIAL_HINTS = 3;

export type Direction = "up" | "right" | "down" | "left";
export type GameStatus = "ready" | "playing" | "paused" | "won" | "lost";
export interface Cell { x: number; y: number }
export interface Snake { id: string; path: Cell[]; active: boolean }
export interface Level { number: number; gridSize: number; seed: number; snakes: Snake[]; solution: string[] }
export interface GameState {
  level: Level;
  snakes: Snake[];
  status: GameStatus;
  lives: number;
  hints: number;
  hintId: string | null;
  remainingMs: number;
  failure: "lives" | "time" | null;
}
export interface TapResult { state: GameState; outcome: "escaped" | "blocked" | "ignored"; snakeId: string }

export const DIRECTION_DELTA: Record<Direction, Cell> = {
  up: { x: 0, y: -1 }, right: { x: 1, y: 0 }, down: { x: 0, y: 1 }, left: { x: -1, y: 0 },
};

/** 将有效关卡序号限制在内置关卡范围，非数字从第一关开始。 */
export function normalizeLevel(number: number): number {
  return Number.isFinite(number) ? Math.max(1, Math.min(LEVEL_COUNT, Math.floor(number))) : 1;
}

/** 按固定种子生成的内置数据创建独立关卡；身体顺序始终为尾到头。 */
export function createLevel(number: number): Level {
  const normalized = normalizeLevel(number);
  const source = levelData[normalized - 1];
  return {
    number: normalized,
    gridSize: source.gridSize,
    seed: source.seed,
    solution: [...source.solution],
    snakes: source.snakes.map((snake) => ({
      id: snake.id,
      active: true,
      path: snake.path.map((cell) => ({ x: cell[0], y: cell[1] })),
    })),
  };
}

/** 创建待开始的关卡，生命、提示和倒计时均独立重置。 */
export function createGame(number: number): GameState {
  const level = createLevel(number);
  return {
    level, snakes: level.snakes, status: "ready", lives: INITIAL_LIVES,
    hints: INITIAL_HINTS, hintId: null, remainingMs: LEVEL_TIME_MS, failure: null,
  };
}

/** 获取最后一段的朝向，关卡中的路径已由回归验证保证相邻。 */
export function snakeDirection(snake: Snake): Direction {
  const head = snake.path[snake.path.length - 1];
  const neck = snake.path[snake.path.length - 2];
  if (head.x > neck.x) return "right";
  if (head.x < neck.x) return "left";
  return head.y > neck.y ? "down" : "up";
}

/** 取得蛇头前方的直线通道；身体沿原路径跟随，不平移整条弯蛇。 */
export function escapeCorridor(snake: Snake, gridSize: number): Cell[] {
  const head = snake.path[snake.path.length - 1];
  const delta = DIRECTION_DELTA[snakeDirection(snake)];
  const own = new Set(snake.path.map((cell) => `${cell.x},${cell.y}`));
  const cells: Cell[] = [];
  // 一条射线最多经过棋盘边长个格子，禁止无界搜索或递归重试。
  for (let step = 1; step <= gridSize; step += 1) {
    const cell = { x: head.x + delta.x * step, y: head.y + delta.y * step };
    if (cell.x < 0 || cell.y < 0 || cell.x >= gridSize || cell.y >= gridSize) break;
    if (!own.has(`${cell.x},${cell.y}`)) cells.push(cell);
  }
  return cells;
}

/** 判断头部通道是否被其他仍在棋盘上的蛇占用，复用上游 MIT 碰撞语义。 */
export function canEscape(snake: Snake, snakes: readonly Snake[], gridSize: number): boolean {
  if (!snake.active) return false;
  const corridor = new Set(escapeCorridor(snake, gridSize).map((cell) => `${cell.x},${cell.y}`));
  return !snakes.some((other) => other.active && other.id !== snake.id
    && other.path.some((cell) => corridor.has(`${cell.x},${cell.y}`)));
}

/** 返回当前可离场的小蛇，供提示和有界可解验证共用。 */
export function availableSnakes(state: Pick<GameState, "snakes" | "level">): Snake[] {
  return state.snakes.filter((snake) => canEscape(snake, state.snakes, state.level.gridSize));
}

/** 移除不会新增障碍，最多移除蛇数量次即可验证整关，无需 DFS。 */
export function solveLevel(level: Level): string[] | null {
  let snakes = level.snakes.map((snake) => ({ ...snake }));
  const solution: string[] = [];
  for (let step = 0; step < level.snakes.length; step += 1) {
    const next = snakes.find((snake) => canEscape(snake, snakes, level.gridSize));
    if (!next) return null;
    solution.push(next.id);
    snakes = snakes.map((snake) => snake.id === next.id ? { ...snake, active: false } : snake);
  }
  return solution;
}

/** 点击身体任意位置均尝试离场；撞到其他蛇只扣一次生命且不改布局。 */
export function tapSnake(state: GameState, snakeId: string): TapResult {
  const snake = state.snakes.find((candidate) => candidate.id === snakeId && candidate.active);
  if (state.status !== "playing" || !snake) return { state, outcome: "ignored", snakeId };
  if (!canEscape(snake, state.snakes, state.level.gridSize)) {
    const lives = Math.max(0, state.lives - 1);
    return {
      state: { ...state, lives, hintId: null, status: lives === 0 ? "lost" : "playing", failure: lives === 0 ? "lives" : null },
      outcome: "blocked", snakeId,
    };
  }
  const snakes = state.snakes.map((candidate) => candidate.id === snakeId ? { ...candidate, active: false } : candidate);
  return {
    state: { ...state, snakes, hintId: null, status: snakes.some((candidate) => candidate.active) ? "playing" : "won" },
    outcome: "escaped", snakeId,
  };
}

/** 仅进行中的关卡扣时间，暂停和结束均保留时间；耗尽立即失败。 */
export function elapseTime(state: GameState, elapsedMs: number): GameState {
  if (state.status !== "playing" || !Number.isFinite(elapsedMs) || elapsedMs <= 0) return state;
  const remainingMs = Math.max(0, state.remainingMs - elapsedMs);
  return { ...state, remainingMs, status: remainingMs === 0 ? "lost" : "playing", failure: remainingMs === 0 ? "time" : null };
}

/** 开始或继续关卡不会复活已结束的关卡；暂停只能由进行中进入。 */
export function setPlaying(state: GameState, playing: boolean): GameState {
  if (playing && (state.status === "ready" || state.status === "paused")) return { ...state, status: "playing" };
  if (!playing && state.status === "playing") return { ...state, status: "paused" };
  return state;
}

/** 每关最多三次提示，重复查看当前提示不扣次数，提示一定可安全离场。 */
export function takeHint(state: GameState): GameState {
  if (state.status !== "playing" || state.hints <= 0 || state.hintId !== null) return state;
  const next = availableSnakes(state)[0];
  return next ? { ...state, hints: state.hints - 1, hintId: next.id } : state;
}
