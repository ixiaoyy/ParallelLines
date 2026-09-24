import { describe, expect, it } from "vitest";

import {
  AmbientEngineError,
  FISH_KINDS,
  createInitialState,
  createLevelState,
  createSeededRandom,
  getBlockerIds,
  getLevelConfig,
  getLevelGoal,
  getSelectablePieces,
  hasDiscoverableMatch,
  hasQuickMatch,
  isSafeFieldPoint,
  selectPiece,
  type AmbientGameState,
  type FishKind,
  type PilePiece,
} from "./ambient";

/**
 * Finds one complete same-species triple in a wave.
 * @param pieces Candidate field fish.
 * @returns The first complete triple, or null when none exists.
 */
function findCompleteSet(
  pieces: readonly PilePiece[],
): readonly [PilePiece, PilePiece, PilePiece] | null {
  for (const kind of FISH_KINDS) {
    const [first, second, third] = pieces.filter((piece) => piece.kind === kind);
    if (first && second && third) return [first, second, third];
  }
  return null;
}

/**
 * Counts every visible species in one canonical inventory.
 * @param state Current game state including field and tray fish.
 * @returns Species-to-count map for the complete active wave.
 */
function getInventoryCounts(state: AmbientGameState): ReadonlyMap<FishKind, number> {
  const counts = new Map<FishKind, number>();
  for (const piece of [...state.pieces, ...state.tray]) {
    counts.set(piece.kind, (counts.get(piece.kind) ?? 0) + 1);
  }
  return counts;
}

/**
 * Selects all three fish in one complete set.
 * @param state State containing the target triple.
 * @param random Random source for any resulting wave refresh.
 * @returns The final combined selection result.
 */
function clearOneSet(
  state: AmbientGameState,
  random: ReturnType<typeof createSeededRandom>,
) {
  const triple = findCompleteSet(state.pieces);
  expect(triple).not.toBeNull();
  if (!triple) throw new Error("Expected a complete fish set.");
  let current = state;
  for (const piece of triple.slice(0, 2)) {
    const moved = selectPiece(current, piece.id, random);
    expect(moved.kind).toBe("moved");
    current = moved.state;
  }
  const combined = selectPiece(current, triple[2].id, random);
  expect(combined.kind).toBe("combined");
  if (combined.kind !== "combined") {
    throw new Error("Expected the third fish to combine.");
  }
  return combined;
}

describe("ambient fish engine", () => {
  it("creates a nine-fish opening with three complete visible groups", () => {
    const state = createInitialState(createSeededRandom(42));
    const counts = [...getInventoryCounts(state).values()];

    expect(state.pieces).toHaveLength(9);
    expect(state.level).toBe(1);
    expect(state.levelProgress).toBe(0);
    expect(state.tray).toEqual([]);
    expect(new Set(state.pieces.map((piece) => piece.id)).size).toBe(9);
    expect(counts).toHaveLength(3);
    expect(counts.every((count) => count === 3)).toBe(true);
    expect(state.pieces.every((piece) => piece.layer === 0)).toBe(true);
    expect(state.pieces.every((piece) => piece.blockerIds?.length === 0)).toBe(true);
    expect(state.pieces.every((piece) => Math.abs(piece.rotation) <= 8)).toBe(true);
    expect(state.pieces.every((piece) => isSafeFieldPoint(piece.pile))).toBe(true);
    expect(hasQuickMatch(state.pieces)).toBe(true);
    expect(hasDiscoverableMatch(state.pieces)).toBe(true);
  });

  it("uses the confirmed 3, 5, 8, 13, 21, 34 level goals", () => {
    expect(Array.from({ length: 6 }, (_, index) => getLevelGoal(index + 1)))
      .toEqual([3, 5, 8, 13, 21, 34]);
    expect(Array.from({ length: 6 }, (_, index) =>
      getLevelConfig(index + 1).targetCount
    )).toEqual([3, 5, 8, 13, 21, 34]);
    expect(Array.from({ length: 6 }, (_, index) =>
      getLevelConfig(index + 1).kindCount
    )).toEqual([3, 5, 6, 7, 8, 8]);
    expect(Array.from({ length: 6 }, (_, index) =>
      getLevelConfig(index + 1).pieceCount
    )).toEqual([9, 11, 13, 15, 17, 17]);
    expect(getLevelGoal(999)).toBe(Number.MAX_SAFE_INTEGER);
  });

  it("creates deterministic single-layer S-curve layouts without duplicate points", () => {
    for (let level = 1; level <= 8; level += 1) {
      const seed = 80 + level;
      const state = createLevelState(level, 0, 1, createSeededRandom(seed));
      const repeated = createLevelState(level, 0, 1, createSeededRandom(seed));
      const positions = state.pieces.map((piece) =>
        `${piece.pile.x.toFixed(3)}:${piece.pile.y.toFixed(3)}`
      );
      const xs = state.pieces.map((piece) => piece.pile.x);
      const ys = state.pieces.map((piece) => piece.pile.y);

      expect(repeated).toEqual(state);
      expect(new Set(positions).size).toBe(state.pieces.length);
      expect(state.pieces.every((piece) => piece.layer === 0)).toBe(true);
      expect(state.pieces.every((piece) => getBlockerIds(state.pieces, piece.id).length === 0))
        .toBe(true);
      expect(state.pieces.every((piece) => piece.blockerIds?.length === 0)).toBe(true);
      expect(state.pieces.every((piece) => Math.abs(piece.rotation) <= 8)).toBe(true);
      expect(state.pieces.every((piece) => isSafeFieldPoint(piece.pile))).toBe(true);
      expect(Math.max(...xs) - Math.min(...xs)).toBeGreaterThan(0.4);
      expect(Math.max(...ys) - Math.min(...ys)).toBeGreaterThan(0.4);
    }
  });

  it("makes exactly one species a triple in every later wave", () => {
    for (let level = 2; level <= 8; level += 1) {
      for (let seed = 1; seed <= 16; seed += 1) {
        const state = createLevelState(
          level,
          seed,
          1,
          createSeededRandom(level * 100 + seed),
          Math.min(seed % getLevelGoal(level), getLevelGoal(level) - 1),
        );
        const counts = [...getInventoryCounts(state).values()];
        expect(counts).toHaveLength(getLevelConfig(level).kindCount);
        expect(counts.filter((count) => count === 3)).toHaveLength(1);
        expect(counts.filter((count) => count === 2)).toHaveLength(counts.length - 1);
        expect(hasQuickMatch(state.pieces)).toBe(true);
      }
    }
  });

  it("keeps repeated fish separated along the authored route", () => {
    for (let level = 1; level <= 8; level += 1) {
      const state = createLevelState(level, 0, 1, createSeededRandom(300 + level));
      for (const kind of FISH_KINDS) {
        const indexes = state.pieces.flatMap((piece, index) =>
          piece.kind === kind ? [index] : []
        );
        for (let index = 1; index < indexes.length; index += 1) {
          expect(indexes[index] - indexes[index - 1]).toBeGreaterThan(1);
        }
      }
    }
  });

  it("exposes every fish directly and leaves missing selections unchanged", () => {
    const state = createInitialState(createSeededRandom(7));
    const snapshot = structuredClone(state);

    expect(getSelectablePieces(state.pieces)).toEqual(state.pieces);
    expect(state.pieces.every((piece) => getBlockerIds(state.pieces, piece.id).length === 0))
      .toBe(true);
    const result = selectPiece(state, "absent", createSeededRandom(8));
    expect(result.kind).toBe("missing");
    expect(result.state).toBe(state);
    expect(state).toEqual(snapshot);
  });

  it("requires all three opening groups before advancing", () => {
    const random = createSeededRandom(19);
    let state = createInitialState(random);

    for (let completed = 1; completed <= 3; completed += 1) {
      const result = clearOneSet(state, random);
      expect(result.state.clearCount).toBe(completed);
      if (completed < 3) {
        expect(result.levelAdvanced).toBe(false);
        expect(result.fieldRefreshed).toBe(false);
        expect(result.state.level).toBe(1);
        expect(result.state.levelProgress).toBe(completed);
        expect(result.state.pieces).toHaveLength((3 - completed) * 3);
      } else {
        expect(result.levelAdvanced).toBe(true);
        expect(result.fieldRefreshed).toBe(true);
        expect(result.state.level).toBe(2);
        expect(result.state.levelProgress).toBe(0);
        expect(result.state.pieces).toHaveLength(11);
      }
      state = result.state;
    }
  });

  it("refreshes one unique-triple wave at a time until the later goal is met", () => {
    const random = createSeededRandom(23);
    let state = createLevelState(2, 3, 10, random);

    for (let completed = 1; completed <= 5; completed += 1) {
      const result = clearOneSet(state, random);
      expect(result.fieldRefreshed).toBe(true);
      expect(result.state.clearCount).toBe(3 + completed);
      if (completed < 5) {
        expect(result.levelAdvanced).toBe(false);
        expect(result.state.level).toBe(2);
        expect(result.state.levelProgress).toBe(completed);
        expect(result.state.tray).toEqual([]);
        expect([...getInventoryCounts(result.state).values()].filter(
          (count) => count === 3
        )).toHaveLength(1);
      } else {
        expect(result.levelAdvanced).toBe(true);
        expect(result.state.level).toBe(3);
        expect(result.state.levelProgress).toBe(0);
      }
      state = result.state;
    }
  });

  it("restarts only the current wave and preserves later-level progress on loss", () => {
    const base = createLevelState(3, 11, 101, createSeededRandom(30), 3);
    const target = base.pieces.find((piece) => piece.kind !== "whale");
    expect(target).toBeDefined();
    if (!target) return;
    const tray = [
      { id: "t1", kind: "whale" },
      { id: "t2", kind: "whale" },
      { id: "t3", kind: "sardine" },
      { id: "t4", kind: "sardine" },
      { id: "t5", kind: "koi" },
      { id: "t6", kind: "koi" },
    ] as const;
    const state: AmbientGameState = { ...base, tray };
    const firstNewPieceId = state.nextPieceId;
    const result = selectPiece(state, target.id, createSeededRandom(31));

    expect(result.kind).toBe("lost");
    if (result.kind !== "lost") return;
    expect(result.state.level).toBe(3);
    expect(result.state.levelProgress).toBe(3);
    expect(result.state.clearCount).toBe(11);
    expect(result.state.pieces).toHaveLength(13);
    expect(result.state.pieces[0]?.id).toBe(`fish-${firstNewPieceId}`);
    expect(result.state.tray).toEqual([]);
  });

  it("combines a completing seventh fish before applying loss", () => {
    const base = createInitialState(createSeededRandom(32));
    const target = base.pieces[0];
    const tray = [
      { id: "match-1", kind: target.kind },
      { id: "match-2", kind: target.kind },
      { id: "k1", kind: "koi" },
      { id: "k2", kind: "koi" },
      { id: "s1", kind: "sardine" },
      { id: "p1", kind: "pufferfish" },
    ] as const;
    const result = selectPiece({ ...base, pieces: [target], tray }, target.id);

    expect(result.kind).toBe("combined");
    if (result.kind !== "combined") return;
    expect(result.levelAdvanced).toBe(false);
    expect(result.state.tray).toHaveLength(4);
  });

  it("rejects invalid level progress and random sources", () => {
    expect(() => createLevelState(2, 0, 1, Math.random, 5)).toThrow(RangeError);
    expect(() => createInitialState(() => 1)).toThrow(AmbientEngineError);
    expect(() => createInitialState(() => Number.NaN)).toThrow(AmbientEngineError);
  });
});
