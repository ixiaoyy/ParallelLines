import { expect, test } from "@playwright/test";

import { chooseAiMove, type Difficulty } from "../../src/features/play/generals-soldiers/ai";
import {
  createInitialState,
  legalMoves,
  playMove,
  type Cell,
  type GameState,
} from "../../src/features/play/generals-soldiers/rules";

test("开局站位、将军先行与隔空吃兵符合棋盘规则", () => {
  const start = createInitialState();
  expect(start.board.slice(0, 15)).toEqual(Array(15).fill("soldier"));
  expect(start.board.slice(20)).toEqual(["empty", "general", "general", "general", "empty"]);
  expect(start.turn).toBe("general");

  const moves = legalMoves(start);
  expect(moves).toContainEqual({ from: 21, to: 16, capture: false });
  expect(moves).toContainEqual({ from: 21, to: 11, capture: true });
  expect(playMove(start, 21, 15)).toBeNull();

  const afterCapture = playMove(start, 21, 11);
  expect(afterCapture?.soldiers).toBe(14);
  expect(afterCapture?.board[11]).toBe("general");
  expect(afterCapture?.board[21]).toBe("empty");
  expect(afterCapture?.turn).toBe("soldier");
  expect(start.board[21]).toBe("general");
});

test("将军吃到只剩三兵时获胜", () => {
  const board: Cell[] = Array(25).fill("empty");
  for (const index of [0, 1, 2, 11]) board[index] = "soldier";
  for (const index of [21, 22, 23]) board[index] = "general";
  const state: GameState = { board, turn: "general", soldiers: 4, ply: 18, winner: null, lastMove: null };

  const result = playMove(state, 21, 11);
  expect(result?.soldiers).toBe(3);
  expect(result?.winner).toBe("general");
  expect(legalMoves(result!)).toEqual([]);
});

test("小兵堵住所有将军的正常落点和跳吃路线后获胜", () => {
  const board: Cell[] = Array(25).fill("empty");
  for (const index of [15, 16, 17, 19, 23]) board[index] = "soldier";
  for (const index of [20, 22, 24]) board[index] = "general";
  const state: GameState = { board, turn: "soldier", soldiers: 5, ply: 9, winner: null, lastMove: null };
  expect(legalMoves(state, "general").length).toBeGreaterThan(0);

  const result = playMove(state, 16, 21);
  expect(result?.winner).toBe("soldier");
  expect(result && legalMoves(result, "general")).toEqual([]);
});

test("四档电脑执将军与小兵时均只提交合法走法", () => {
  const start = createInitialState();
  const soldierState = playMove(start, 21, 16);
  expect(soldierState).not.toBeNull();
  const difficulties: Difficulty[] = ["easy", "normal", "hard", "hell"];

  for (const difficulty of difficulties) {
    for (const position of [start, soldierState!]) {
      const result = chooseAiMove(position, difficulty, [], () => 0.8);
      expect(result.move, `${difficulty}/${position.turn}`).not.toBeNull();
      expect(legalMoves(position), `${difficulty}/${position.turn}`).toContainEqual(result.move);
      expect(result.depth, `${difficulty}/${position.turn}`).toBeGreaterThan(0);
    }
  }
});

test("四档电脑遇到当前一步可赢的局面会直接取胜", () => {
  const generalBoard: Cell[] = Array(25).fill("empty");
  for (const index of [0, 1, 2, 11]) generalBoard[index] = "soldier";
  for (const index of [21, 22, 23]) generalBoard[index] = "general";
  const generalState: GameState = {
    board: generalBoard, turn: "general", soldiers: 4, ply: 18, winner: null, lastMove: null,
  };

  const soldierBoard: Cell[] = Array(25).fill("empty");
  for (const index of [15, 16, 17, 19, 23]) soldierBoard[index] = "soldier";
  for (const index of [20, 22, 24]) soldierBoard[index] = "general";
  const soldierState: GameState = {
    board: soldierBoard, turn: "soldier", soldiers: 5, ply: 9, winner: null, lastMove: null,
  };

  for (const difficulty of ["easy", "normal", "hard", "hell"] as const) {
    const generalMove = chooseAiMove(generalState, difficulty, [], () => 0);
    expect(generalMove.move, difficulty).toEqual({ from: 21, to: 11, capture: true });

    const soldierMove = chooseAiMove(soldierState, difficulty, [], () => 0);
    expect(soldierMove.move, difficulty).toEqual({ from: 16, to: 21, capture: false });
  }
});

test("四档电脑在固定战术局面会因前瞻能力改变决策", () => {
  const position = (rows: string[], turn: GameState["turn"], ply: number): GameState => {
    const board = rows.join("").split("").map((mark): Cell =>
      mark === "G" ? "general" : mark === "S" ? "soldier" : "empty",
    );
    return { board, turn, soldiers: board.filter((cell) => cell === "soldier").length, ply, winner: null, lastMove: null };
  };
  const situations = [
    { rows: ["SSSSS", "SSSSS", "SG.SS", ".....", ".GSG."], turn: "general", ply: 4, weaker: "easy", stronger: "normal" },
    { rows: ["SSSSS", "SSSSS", "...GS", "SG...", ".GS.."], turn: "soldier", ply: 7, weaker: "normal", stronger: "hard" },
    { rows: ["SSSSS", "SSSSS", "S..SS", ".G...", ".GSG."], turn: "soldier", ply: 5, weaker: "hard", stronger: "hell" },
  ] as const;

  for (const situation of situations) {
    const state = position(situation.rows, situation.turn, situation.ply);
    const shallow = chooseAiMove(state, situation.weaker, [], () => 0.99);
    const deeper = chooseAiMove(state, situation.stronger, [], () => 0.99);
    expect(shallow.move, `${situation.weaker}/${situation.stronger}`).not.toEqual(deeper.move);
    expect(deeper.depth).toBeGreaterThanOrEqual(shallow.depth);
  }
});
