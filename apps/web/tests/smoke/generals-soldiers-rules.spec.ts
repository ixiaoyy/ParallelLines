import { expect, test } from "@playwright/test";

import { chooseAiMove, type Difficulty } from "../../src/features/play/generals-soldiers/ai";
import {
  createInitialState,
  legalMoves,
  playMove,
  positionKey,
  type Cell,
  type GameState,
} from "../../src/features/play/generals-soldiers/rules";

/** 用固定棋盘构造回归局面，G 为将军、S 为小兵、点号为空格。 */
function position(rows: readonly string[], turn: GameState["turn"], ply: number): GameState {
  const board = rows.join("").split("").map((mark): Cell =>
    mark === "G" ? "general" : mark === "S" ? "soldier" : "empty",
  );
  return { board, turn, soldiers: board.filter((cell) => cell === "soldier").length, ply, winner: null, lastMove: null };
}

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

test("困难与最高难度将军在围堵前先救出角落将军", () => {
  const state = position(["GS..S", ".S.SS", ".SSGS", "...S.", "..G.."], "general", 26);

  // 自弈中的旧走法先吃兵，会给小兵封死左上角将军的机会；此时仍可主动撤出。
  const greedy = playMove(state, 22, 12);
  expect(greedy).not.toBeNull();
  const blocked = playMove(greedy!, 6, 5);
  expect(blocked).not.toBeNull();
  expect(legalMoves(blocked!, "general").filter((move) => move.from === 0)).toEqual([]);
  expect(legalMoves(state)).toContainEqual({ from: 0, to: 5, capture: false });

  for (const difficulty of ["hard", "hell"] as const) {
    const result = chooseAiMove(state, difficulty, [], () => 0.99);
    expect(result.move, difficulty).toEqual({ from: 0, to: 5, capture: false });
    const escaped = playMove(state, result.move!.from, result.move!.to)!;
    expect(escaped.soldiers).toBe(state.soldiers);

    // 检查全部下一手兵方应对，确认撤退后的将军不会立刻被封死。
    for (const reply of legalMoves(escaped)) {
      const afterReply = playMove(escaped, reply.from, reply.to)!;
      expect(legalMoves(afterReply, "general").some((move) => move.from === 5), difficulty).toBe(true);
    }
  }
});

test("高难度将军仍会选择落入角落但立即获胜的吃兵", () => {
  const state = position(["SS...", ".S...", "G....", ".....", "..GGS"], "general", 60);

  // 落点紧邻封锁兵，吃完却只剩三兵；胜负应先于退路风险决定走法。
  for (const difficulty of ["hard", "hell"] as const) {
    const result = chooseAiMove(state, difficulty, [], () => 0.99);
    expect(result.move, difficulty).toEqual({ from: 10, to: 0, capture: true });
    const won = playMove(state, result.move!.from, result.move!.to)!;
    expect(won.soldiers).toBe(3);
    expect(won.winner).toBe("general");
    expect(legalMoves(won)).toEqual([]);
  }
});

test("电脑小兵各难度和低难度将军保留原有固定战术选择", () => {
  const general = position(["SSSSS", "SSSSS", "SG.SS", ".....", ".GSG."], "general", 4);
  const soldier = position(["SSSSS", "SSSSS", "S..SS", ".G...", ".GSG."], "soldier", 5);

  // 期望值来自增强前的固定局面，防止将军防守评分外溢到未授权修改的难度和阵营。
  const unchanged = [
    { state: general, difficulty: "easy", move: { from: 23, to: 13, capture: true } },
    { state: general, difficulty: "normal", move: { from: 11, to: 13, capture: true } },
    { state: soldier, difficulty: "easy", move: { from: 6, to: 11, capture: false } },
    { state: soldier, difficulty: "normal", move: { from: 13, to: 12, capture: false } },
    { state: soldier, difficulty: "hard", move: { from: 13, to: 12, capture: false } },
    { state: soldier, difficulty: "hell", move: { from: 10, to: 11, capture: false } },
  ] as const;

  for (const situation of unchanged) {
    const result = chooseAiMove(situation.state, situation.difficulty, [], () => 0.99);
    expect(result.move, `${situation.state.turn}/${situation.difficulty}`).toEqual(situation.move);
  }
});

test("最高难度避开八半步后才会被全部封锁的走法", () => {
  const state = position([".S..S", ".S..S", "SGS.S", "S.S..", ".GGS."], "general", 42);

  // 失败棋谱第42手：11→16在八半步内会被强制封死，21→16仍有退路。
  expect(legalMoves(state)).toContainEqual({ from: 11, to: 16, capture: false });
  const result = chooseAiMove(state, "hell", [], () => 0.99);
  expect(result.move).toEqual({ from: 21, to: 16, capture: false });
  expect(legalMoves(state)).toContainEqual(result.move);
  expect(result.nodes).toBeLessThanOrEqual(160_001);
});

test("所有候选已被证明必败时仍返回合法走法并由规则判胜负", () => {
  const state = position(["..S.S", ".S..S", "SS..S", ".GS..", "SGGS."], "general", 48);
  expect(legalMoves(state)).toEqual([{ from: 16, to: 15, capture: false }]);

  // 该局只剩一条必败退路；筛掉已证败候选后不能把仍在进行的对局当成无棋可走。
  for (const difficulty of ["hard", "hell"] as const) {
    const result = chooseAiMove(state, difficulty, [], () => 0.99);
    expect(result.move, difficulty).toEqual({ from: 16, to: 15, capture: false });
    const continued = playMove(state, result.move!.from, result.move!.to)!;
    expect(continued.winner).toBeNull();
    const blocked = playMove(continued, 11, 16);
    expect(blocked?.winner).toBe("soldier");
  }
});

test("历史局面键不会覆盖立即获胜和已经结束的真实终局", () => {
  const state = position(["SS...", ".S...", "G....", ".....", "..GGS"], "general", 60);
  const won = playMove(state, 10, 0)!;
  const recent = [positionKey(won)];

  // 历史键不带胜负标记；即使传入的历史包含胜局棋盘，真实终局仍必须优先。
  for (const difficulty of ["hard", "hell"] as const) {
    const result = chooseAiMove(state, difficulty, recent, () => 0.99);
    expect(result.move, difficulty).toEqual({ from: 10, to: 0, capture: true });
    expect(playMove(state, result.move!.from, result.move!.to)?.winner).toBe("general");
    expect(chooseAiMove(won, difficulty, recent, () => 0.99)).toEqual({ move: null, depth: 0, nodes: 0 });
  }
});
