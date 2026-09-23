export const BOARD_SIZE = 5;
export const CELL_COUNT = BOARD_SIZE * BOARD_SIZE;

export type Side = "general" | "soldier";
export type Cell = "empty" | Side;
export type Winner = Side | null;

export interface Move {
  from: number;
  to: number;
  capture: boolean;
}

export interface GameState {
  board: Cell[];
  turn: Side;
  soldiers: number;
  ply: number;
  winner: Winner;
  lastMove: Move | null;
}

const DIRECTIONS = [
  [-1, 0],
  [1, 0],
  [0, -1],
  [0, 1],
] as const;

function indexAt(row: number, column: number): number {
  return row * BOARD_SIZE + column;
}

function inBoard(row: number, column: number): boolean {
  return row >= 0 && row < BOARD_SIZE && column >= 0 && column < BOARD_SIZE;
}

/** 建立固定开局：顶部三排小兵、底行中间三名将军，由将军先走。 */
export function createInitialState(): GameState {
  const board: Cell[] = Array.from({ length: CELL_COUNT }, (_, index) =>
    index < BOARD_SIZE * 3 ? "soldier" : "empty",
  );
  board[indexAt(4, 1)] = "general";
  board[indexAt(4, 2)] = "general";
  board[indexAt(4, 3)] = "general";
  return { board, turn: "general", soldiers: 15, ply: 0, winner: null, lastMove: null };
}

/** 列出指定一方当前全部合法走法；将军跳吃须隔一个空格，落在小兵原位。 */
export function legalMoves(state: GameState, side: Side = state.turn): Move[] {
  if (state.winner) return [];
  const moves: Move[] = [];

  for (let from = 0; from < CELL_COUNT; from += 1) {
    if (state.board[from] !== side) continue;
    const row = Math.floor(from / BOARD_SIZE);
    const column = from % BOARD_SIZE;

    for (const [deltaRow, deltaColumn] of DIRECTIONS) {
      const nearRow = row + deltaRow;
      const nearColumn = column + deltaColumn;
      if (!inBoard(nearRow, nearColumn)) continue;
      const near = indexAt(nearRow, nearColumn);
      if (state.board[near] !== "empty") continue;

      moves.push({ from, to: near, capture: false });

      // 将军可选择正常走一步，也可沿同方向越过这个空格吃第二格的小兵。
      if (side === "general") {
        const farRow = nearRow + deltaRow;
        const farColumn = nearColumn + deltaColumn;
        if (inBoard(farRow, farColumn)) {
          const far = indexAt(farRow, farColumn);
          if (state.board[far] === "soldier") {
            moves.push({ from, to: far, capture: true });
          }
        }
      }
    }
  }

  return moves;
}

/** 应用由 legalMoves 产生的一步棋；无步可走的小兵方自动跳过，不增加胜负条件。 */
export function applyLegalMove(state: GameState, move: Move): GameState {
  const board = [...state.board];
  board[move.from] = "empty";
  board[move.to] = state.turn;
  const soldiers = state.soldiers - (move.capture ? 1 : 0);
  const next: GameState = {
    board,
    turn: state.turn === "general" ? "soldier" : "general",
    soldiers,
    ply: state.ply + 1,
    winner: null,
    lastMove: move,
  };

  // 截图规定仅有两种胜利：小兵剩三枚以下，或全部将军无法移动和跳吃。
  if (soldiers <= 3) {
    next.winner = "general";
    return next;
  }
  if (legalMoves(next, "general").length === 0) {
    next.winner = "soldier";
    return next;
  }

  if (next.turn === "soldier" && legalMoves(next, "soldier").length === 0) {
    next.turn = "general";
    next.ply += 1;
  }
  return next;
}

/** 验证玩家或电脑提交的起止格，再用同一套规则推进棋局。 */
export function playMove(state: GameState, from: number, to: number): GameState | null {
  const move = legalMoves(state).find((candidate) => candidate.from === from && candidate.to === to);
  return move ? applyLegalMove(state, move) : null;
}

/** 生成包含轮到谁走的局面键，仅供电脑避免反复来回。 */
export function positionKey(state: GameState): string {
  return `${state.turn}:${state.board.map((cell) => cell[0]).join("")}`;
}
