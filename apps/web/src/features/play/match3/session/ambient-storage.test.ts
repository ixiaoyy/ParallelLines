import { describe, expect, it } from "vitest";

import {
  FISH_KINDS,
  createLevelState,
  createSeededRandom,
  selectPiece,
  type PilePiece,
} from "../engine";
import {
  AMBIENT_STORAGE_KEY,
  createFreshSnapshot,
  loadAmbientSnapshot,
  loadAmbientSnapshotResult,
  parseAmbientSnapshot,
  saveAmbientSnapshot,
  type StorageLike,
} from "./ambient-storage";

const LEGACY_KIND_BY_FISH = {
  whale: "aqua",
  koi: "amber",
  sardine: "lime",
  pufferfish: "rose",
  goldfish: "goldfish",
  clownfish: "clownfish",
  angelfish: "angelfish",
  betta: "betta",
} as const;

/**
 * Creates deterministic in-memory storage for snapshot tests.
 * @returns A storage adapter with inspectable serialized values.
 */
function createMemoryStorage(): StorageLike & { values: Map<string, string> } {
  const values = new Map<string, string>();
  return {
    values,
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
  };
}

/**
 * Builds a pre-redesign all-triples inventory for v1-v4 compatibility tests.
 * @param kindCount Number of legacy species included.
 * @param copiesPerKind Complete triple multiples allocated to each species.
 * @returns Canonical-looking legacy pieces with unique IDs and valid geometry.
 */
function createLegacyTriplePieces(
  kindCount: number,
  copiesPerKind = 3,
): readonly PilePiece[] {
  const templates = createLevelState(5, 0, 1, createSeededRandom(700)).pieces;
  return FISH_KINDS.slice(0, kindCount).flatMap((kind, kindIndex) =>
    Array.from({ length: copiesPerKind }, (_, copyIndex) => {
      const template = templates[(kindIndex * copiesPerKind + copyIndex) % templates.length];
      if (!template) throw new Error("Expected a legacy geometry template.");
      return {
        ...template,
        id: `legacy-${kindIndex}-${copyIndex}`,
        kind,
        layer: (copyIndex % 3) as 0 | 1 | 2,
        blockerIds: [],
      };
    })
  );
}

/**
 * Converts current fish names to the v1/v2 species vocabulary.
 * @param pieces Current-kind legacy pieces.
 * @returns JSON-ready pieces using the historical species identifiers.
 */
function useLegacyKindNames(pieces: readonly PilePiece[]) {
  return pieces.map((piece) => ({
    ...piece,
    kind: LEGACY_KIND_BY_FISH[piece.kind],
  }));
}

describe("ambient snapshot storage", () => {
  it("reports whether a valid snapshot was restored or a fresh fallback was used", () => {
    const storage = createMemoryStorage();
    const emptyResult = loadAmbientSnapshotResult(
      storage,
      createSeededRandom(8),
      2_000,
    );
    expect(emptyResult).toEqual({
      snapshot: createFreshSnapshot(createSeededRandom(8), 2_000),
      loadedFromStorage: false,
    });

    const storedSnapshot = createFreshSnapshot(createSeededRandom(9), 3_000);
    expect(saveAmbientSnapshot(storage, storedSnapshot)).toBe(true);
    expect(loadAmbientSnapshotResult(storage, createSeededRandom(10), 4_000))
      .toEqual({ snapshot: storedSnapshot, loadedFromStorage: true });

    storage.values.set(AMBIENT_STORAGE_KEY, "not-json");
    expect(loadAmbientSnapshotResult(storage, createSeededRandom(11), 5_000))
      .toEqual({
        snapshot: createFreshSnapshot(createSeededRandom(11), 5_000),
        loadedFromStorage: false,
      });
  });

  it("round-trips a partially selected wave including level progress", () => {
    const storage = createMemoryStorage();
    const fresh = createFreshSnapshot(createSeededRandom(10));
    const target = fresh.game.pieces[0];
    expect(target).toBeDefined();
    if (!target) return;
    const selection = selectPiece(fresh.game, target.id, createSeededRandom(11));
    const snapshot = {
      ...fresh,
      game: selection.state,
      preferences: { soundEnabled: true },
      pet: { guardedPieceId: null, fishFedCount: 27 },
    };

    expect(saveAmbientSnapshot(storage, snapshot)).toBe(true);
    expect(loadAmbientSnapshot(storage, createSeededRandom(12))).toEqual(snapshot);
    expect(parseAmbientSnapshot(snapshot)?.game.levelProgress).toBe(0);
  });

  it("normalizes a full tray into the same opening wave without losing durable progress", () => {
    const storage = createMemoryStorage();
    const fresh = createFreshSnapshot(createSeededRandom(15), 5_000);
    const traySources = fresh.game.pieces.slice(0, 7);
    const snapshot = {
      ...fresh,
      game: {
        ...fresh.game,
        pieces: fresh.game.pieces.slice(7),
        tray: traySources.map(({ id, kind }) => ({ id, kind })),
        clearCount: 24,
      },
      preferences: { soundEnabled: true },
      pet: { guardedPieceId: null, fishFedCount: 41 },
    };
    expect(saveAmbientSnapshot(storage, snapshot)).toBe(true);

    const restored = loadAmbientSnapshot(storage, createSeededRandom(16), 9_000);
    expect(restored.game.level).toBe(1);
    expect(restored.game.levelProgress).toBe(0);
    expect(restored.game.pieces).toHaveLength(9);
    expect(restored.game.pieces[0]?.id).toBe(`fish-${fresh.game.nextPieceId}`);
    expect(restored.game.tray).toEqual([]);
    expect(restored.game.clearCount).toBe(24);
    expect(restored.game.nextPieceId).toBe(fresh.game.nextPieceId + 9);
    expect(restored.plant.plantedAt).toBe(5_000);
    expect(restored.preferences.soundEnabled).toBe(true);
    expect(restored.pet).toEqual({ guardedPieceId: null, fishFedCount: 41 });
  });

  it("reads an old version-four all-triples board and defaults its wave progress", () => {
    const oldGame = {
      pieces: createLegacyTriplePieces(3, 12),
      tray: [],
      clearCount: 24,
      level: 1,
      nextPieceId: 200,
    };
    const oldSnapshot = {
      version: 4,
      game: oldGame,
      preferences: { soundEnabled: true },
      plant: { plantedAt: 5_000 },
      pet: { guardedPieceId: null, fishFedCount: 41 },
    };
    const parsed = parseAmbientSnapshot(oldSnapshot);

    expect(parsed?.game.pieces).toHaveLength(36);
    expect(parsed?.game.levelProgress).toBe(0);
    expect(parsed?.game.clearCount).toBe(24);
    expect(parsed?.pet.fishFedCount).toBe(41);
  });

  it("migrates a version-three feed snapshot into a current unique-triple wave", () => {
    const storage = createMemoryStorage();
    const pieces = [...createLegacyTriplePieces(6)];
    const fedSource = pieces.shift();
    expect(fedSource).toBeDefined();
    if (!fedSource) return;
    storage.values.set(AMBIENT_STORAGE_KEY, JSON.stringify({
      version: 3,
      game: {
        pieces,
        tray: [],
        fed: [{ id: fedSource.id, kind: fedSource.kind, settled: false }],
        clearCount: 17,
        level: 3,
        nextPieceId: 90,
      },
      preferences: { soundEnabled: true },
      plant: { plantedAt: 6_000 },
      pet: { guardedPieceId: pieces[0]?.id ?? null },
    }));

    const restored = loadAmbientSnapshot(storage, createSeededRandom(45));
    const counts = FISH_KINDS.map((kind) =>
      restored.game.pieces.filter((piece) => piece.kind === kind).length
    ).filter((count) => count > 0);
    expect(restored.version).toBe(4);
    expect(restored.game.level).toBe(3);
    expect(restored.game.levelProgress).toBe(0);
    expect(restored.game.clearCount).toBe(17);
    expect(restored.game.pieces).toHaveLength(13);
    expect(counts.filter((count) => count === 3)).toHaveLength(1);
    expect(counts.filter((count) => count === 2)).toHaveLength(5);
    expect(restored.pet).toEqual({ guardedPieceId: null, fishFedCount: 1 });
    expect(restored.preferences.soundEnabled).toBe(true);
    expect(restored.plant.plantedAt).toBe(6_000);
  });

  it("migrates version-two species names while preserving progress", () => {
    for (const [level, kindCount] of [[2, 4], [6, 8]] as const) {
      const storage = createMemoryStorage();
      const pieces = createLegacyTriplePieces(kindCount);
      storage.values.set(AMBIENT_STORAGE_KEY, JSON.stringify({
        version: 2,
        game: {
          pieces: useLegacyKindNames(pieces),
          tray: [],
          clearCount: 12,
          level,
          nextPieceId: 120,
        },
        preferences: { soundEnabled: false },
        plant: { plantedAt: 5_000 },
      }));

      const restored = loadAmbientSnapshot(storage, createSeededRandom(level));
      expect(restored.game.level).toBe(level);
      expect(restored.game.clearCount).toBe(12);
      expect(restored.game.levelProgress).toBe(0);
      expect(restored.game.pieces).toHaveLength(level === 2 ? 11 : 17);
      expect(restored.pet.fishFedCount).toBe(0);
    }
  });

  it("migrates an eighteen-piece version-one snapshot", () => {
    const storage = createMemoryStorage();
    const pieces = createLegacyTriplePieces(3, 6);
    storage.values.set(AMBIENT_STORAGE_KEY, JSON.stringify({
      version: 1,
      game: {
        pieces: useLegacyKindNames(pieces),
        tray: [],
        clearCount: 432,
        nextPieceId: 90,
      },
      preferences: { soundEnabled: false },
    }));

    const restored = loadAmbientSnapshot(storage, createSeededRandom(14), 86_401_000);
    expect(restored.game.level).toBe(1);
    expect(restored.game.pieces).toHaveLength(9);
    expect(restored.game.clearCount).toBe(432);
    expect(restored.plant.plantedAt).toBe(86_401_000);
  });

  it("restores only guards that still point to a current fish", () => {
    const fresh = createFreshSnapshot(createSeededRandom(46));
    const target = fresh.game.pieces[0];
    expect(target).toBeDefined();
    if (!target) return;

    expect(parseAmbientSnapshot({
      ...fresh,
      pet: { guardedPieceId: target.id, fishFedCount: 100 },
    })?.pet.guardedPieceId).toBe(target.id);
    expect(parseAmbientSnapshot({
      ...fresh,
      pet: { guardedPieceId: "missing-fish", fishFedCount: 100 },
    })?.pet.guardedPieceId).toBeNull();
    expect(parseAmbientSnapshot({
      ...fresh,
      pet: { guardedPieceId: 42, fishFedCount: 100 },
    })?.pet.guardedPieceId).toBeNull();
    expect(parseAmbientSnapshot({
      ...fresh,
      pet: { guardedPieceId: null, fishFedCount: -1 },
    })).toBeNull();
  });

  it.each([
    "not-json",
    JSON.stringify({ version: 5 }),
    JSON.stringify({ version: 4 }),
    JSON.stringify({ version: 3 }),
    JSON.stringify({ version: 2, game: {}, preferences: { soundEnabled: false } }),
  ])("falls back for malformed or incompatible data", (raw) => {
    const storage = createMemoryStorage();
    storage.values.set(AMBIENT_STORAGE_KEY, raw);
    const snapshot = loadAmbientSnapshot(storage, createSeededRandom(20));

    expect(snapshot.version).toBe(4);
    expect(snapshot.game.pieces).toHaveLength(9);
    expect(snapshot.game.levelProgress).toBe(0);
    expect(snapshot.preferences.soundEnabled).toBe(false);
  });

  it("rejects invalid geometry, inventory, tray bounds, and counters", () => {
    const valid = createFreshSnapshot(createSeededRandom(30));
    expect(parseAmbientSnapshot({
      ...valid,
      game: {
        ...valid.game,
        pieces: valid.game.pieces.map((piece, index) =>
          index === 1 ? { ...piece, id: valid.game.pieces[0]?.id } : piece
        ),
      },
    })).toBeNull();
    expect(parseAmbientSnapshot({
      ...valid,
      game: {
        ...valid.game,
        pieces: valid.game.pieces.map((piece, index) =>
          index === 0 ? { ...piece, pile: { ...piece.pile, x: 4 } } : piece
        ),
      },
    })).toBeNull();
    expect(parseAmbientSnapshot({
      ...valid,
      game: { ...valid.game, clearCount: -1 },
    })).toBeNull();
    expect(parseAmbientSnapshot({
      ...valid,
      game: { ...valid.game, levelProgress: 3 },
    })).toBeNull();
    expect(parseAmbientSnapshot({
      ...valid,
      game: {
        ...valid.game,
        pieces: valid.game.pieces.map((piece, index) =>
          index === 0
            ? { ...piece, kind: piece.kind === "whale" ? "koi" as const : "whale" as const }
            : piece
        ),
      },
    })).toBeNull();
    expect(parseAmbientSnapshot({
      ...valid,
      game: {
        ...valid.game,
        tray: Array.from({ length: 8 }, (_, index) => ({
          id: `tray-${index}`,
          kind: "whale" as const,
        })),
      },
    })).toBeNull();
    expect(parseAmbientSnapshot({
      ...valid,
      plant: { plantedAt: -1 },
    })).toBeNull();
  });

  it("keeps in-memory play available when storage throws", () => {
    const storage: StorageLike = {
      getItem: () => {
        throw new Error("blocked");
      },
      setItem: () => {
        throw new Error("quota");
      },
    };
    const snapshot = loadAmbientSnapshot(storage, createSeededRandom(40));

    expect(snapshot.game.pieces).toHaveLength(9);
    expect(saveAmbientSnapshot(storage, snapshot)).toBe(false);
  });
});
