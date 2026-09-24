import { randomBetween, sampleIndex, shuffle } from "./ambient-random";
import {
  FISH_KINDS,
  type AmbientGameState,
  type FishKind,
  type PilePiece,
  type Point,
  type RandomSource,
} from "./ambient-types";

export interface LevelConfig {
  readonly pieceCount: 9 | 11 | 13 | 15 | 17;
  readonly kindCount: 3 | 5 | 6 | 7 | 8;
  readonly targetCount: number;
}

export const INITIAL_DISCOVERY_POINT: Point = Object.freeze({ x: 0.5, y: 0.45 });
export const DISCOVERY_RADIUS_X = 0.18;
export const DISCOVERY_RADIUS_Y = 0.24;

// Kept at the legacy ceiling so existing v4 snapshots can be read long enough
// to preserve their durable plant, pet, and sound progress.
export const MAX_PIECE_COUNT = 60;

const FIELD_MIN_X = 0.06;
const FIELD_MAX_X = 0.9;
const FIELD_MIN_Y = 0.08;
const FIELD_MAX_Y = 0.8;
const RESERVED_CORNER_MIN_X = 0.72;
const RESERVED_CORNER_MAX_Y = 0.36;

const SCHOOL_POINTS: readonly Point[] = Object.freeze([
  { x: 0.2, y: 0.14 },
  { x: 0.32, y: 0.12 },
  { x: 0.45, y: 0.16 },
  { x: 0.58, y: 0.23 },
  { x: 0.53, y: 0.32 },
  { x: 0.4, y: 0.3 },
  { x: 0.27, y: 0.31 },
  { x: 0.15, y: 0.39 },
  { x: 0.23, y: 0.48 },
  { x: 0.36, y: 0.51 },
  { x: 0.5, y: 0.48 },
  { x: 0.63, y: 0.42 },
  { x: 0.59, y: 0.56 },
  { x: 0.49, y: 0.65 },
  { x: 0.36, y: 0.71 },
  { x: 0.23, y: 0.69 },
  { x: 0.12, y: 0.6 },
]);

const SCHOOL_POINT_INDEXES = Object.freeze({
  9: [0, 2, 4, 6, 8, 10, 12, 14, 16],
  11: [0, 1, 3, 5, 6, 8, 9, 11, 13, 15, 16],
  13: [0, 1, 2, 4, 5, 6, 8, 9, 10, 12, 13, 15, 16],
  15: [0, 1, 2, 3, 4, 6, 7, 8, 9, 10, 11, 12, 14, 15, 16],
  17: SCHOOL_POINTS.map((_, index) => index),
} satisfies Readonly<Record<LevelConfig["pieceCount"], readonly number[]>>);

/**
 * Validates that a normalized point stays inside the fish field and outside
 * the reserved cat-and-plant corner.
 * @param point Normalized field point to validate.
 * @returns Whether the point is safe for an independently clickable fish.
 */
export function isSafeFieldPoint(point: Point): boolean {
  return Number.isFinite(point.x) &&
    Number.isFinite(point.y) &&
    point.x >= FIELD_MIN_X &&
    point.x <= FIELD_MAX_X &&
    point.y >= FIELD_MIN_Y &&
    point.y <= FIELD_MAX_Y &&
    !(point.x > RESERVED_CORNER_MIN_X && point.y < RESERVED_CORNER_MAX_Y);
}

/**
 * Returns the number of triples required to finish a level.
 * @param level Positive one-based level number.
 * @returns The 3, 5, 8, 13, 21, 34… progression for that level.
 */
export function getLevelGoal(level: number): number {
  if (!Number.isSafeInteger(level) || level < 1) {
    throw new RangeError("Level must be a positive safe integer.");
  }
  if (level === 1) return 3;
  if (level > 74) return Number.MAX_SAFE_INTEGER;
  let previous = 3;
  let current = 5;
  for (let currentLevel = 2; currentLevel < level; currentLevel += 1) {
    const next = Math.min(Number.MAX_SAFE_INTEGER, previous + current);
    previous = current;
    current = next;
  }
  return current;
}

/**
 * Describes one authored fish-school wave and its completion target.
 * @param level Positive one-based level number.
 * @returns Fish count, species count, and triples needed for the level.
 */
export function getLevelConfig(level: number): LevelConfig {
  const targetCount = getLevelGoal(level);
  if (level === 1) {
    return { pieceCount: 9, kindCount: 3, targetCount };
  }
  const kindCount = Math.min(8, level + 3) as LevelConfig["kindCount"];
  const pieceCount = (kindCount * 2 + 1) as LevelConfig["pieceCount"];
  return { pieceCount, kindCount, targetCount };
}

/**
 * Rotates a shuffled species pass so adjacent passes do not repeat a kind and
 * an optional kind is kept away from the final slot.
 * @param kinds Species included in this pass.
 * @param previousKind Last scheduled species, if any.
 * @param avoidLastKind Species reserved for one extra trailing occurrence.
 * @param random Random source used for the initial order.
 * @returns One complete, safely rotated species pass.
 */
function createKindPass(
  kinds: readonly FishKind[],
  previousKind: FishKind | null,
  avoidLastKind: FishKind | null,
  random: RandomSource,
): readonly FishKind[] {
  const order = shuffle(random, kinds);
  for (let offset = 0; offset < order.length; offset += 1) {
    const rotated = [...order.slice(offset), ...order.slice(0, offset)];
    if (
      rotated[0] !== previousKind &&
      (!avoidLastKind || rotated.at(-1) !== avoidLastKind)
    ) {
      return rotated;
    }
  }
  return order;
}

/**
 * Interleaves identical fish across the full migration route.
 * @param activeKinds Species visible in this wave.
 * @param targetKind The only later-level species with a third fish, or null for level one.
 * @param random Random source used to vary species order without changing geometry.
 * @returns A schedule whose repeated species are spatially separated.
 */
function createKindSchedule(
  activeKinds: readonly FishKind[],
  targetKind: FishKind | null,
  random: RandomSource,
): readonly FishKind[] {
  const passCount = targetKind ? 2 : 3;
  const schedule: FishKind[] = [];
  for (let passIndex = 0; passIndex < passCount; passIndex += 1) {
    const pass = createKindPass(
      activeKinds,
      schedule.at(-1) ?? null,
      targetKind && passIndex === passCount - 1 ? targetKind : null,
      random,
    );
    schedule.push(...pass);
  }
  if (targetKind) schedule.push(targetKind);
  return schedule;
}

/**
 * Selects the authored S-curve points that preserve full-field coverage for a
 * specific wave size.
 * @param pieceCount Number of fish rendered in the wave.
 * @returns Stable normalized positions with no gameplay overlap.
 */
function createSchoolPoints(pieceCount: LevelConfig["pieceCount"]): readonly Point[] {
  return SCHOOL_POINT_INDEXES[pieceCount].map((index) => SCHOOL_POINTS[index]);
}

/**
 * Creates one single-layer felt fish at an authored school point.
 * @param id Monotonic canonical fish number.
 * @param kind Species assigned by the wave schedule.
 * @param random Random source for restrained scale and tilt variation.
 * @param fieldPoint Stable normalized school position.
 * @returns One independently selectable canonical fish.
 */
function createPiece(
  id: number,
  kind: FishKind,
  random: RandomSource,
  fieldPoint: Point,
): PilePiece {
  return {
    id: `fish-${id}`,
    kind,
    pile: fieldPoint,
    spread: fieldPoint,
    rotation: randomBetween(random, -8, 8),
    scale: randomBetween(random, 0.96, 1.06),
    layer: 0,
    blockerIds: [],
  };
}

/**
 * Creates the current level's opening field or later unique-triple wave.
 * @param level Positive one-based level number.
 * @param clearCount Lifetime completed-triple count.
 * @param nextPieceId First canonical fish number available to this wave.
 * @param random Random source for species order and restrained visual variation.
 * @param levelProgress Triples already completed inside this level.
 * @returns A fresh wave with an empty tray.
 */
export function createLevelState(
  level: number,
  clearCount: number,
  nextPieceId: number,
  random: RandomSource = Math.random,
  levelProgress = 0,
): AmbientGameState {
  const config = getLevelConfig(level);
  if (
    !Number.isSafeInteger(levelProgress) ||
    levelProgress < 0 ||
    levelProgress >= config.targetCount
  ) {
    throw new RangeError("Level progress must be inside the active level target.");
  }
  const activeKinds = shuffle(random, FISH_KINDS).slice(0, config.kindCount);
  const targetKind = level === 1
    ? null
    : activeKinds[sampleIndex(random, activeKinds.length)];
  const kindSchedule = createKindSchedule(activeKinds, targetKind, random);
  const positions = createSchoolPoints(config.pieceCount);
  const pieces = kindSchedule.map((kind, offset) =>
    createPiece(nextPieceId + offset, kind, random, positions[offset])
  );

  return {
    pieces,
    tray: [],
    clearCount,
    level,
    levelProgress,
    nextPieceId: nextPieceId + pieces.length,
  };
}

/**
 * Creates a fresh first-level three-triple field.
 * @param random Random source used for species and visual variation.
 * @returns Initial canonical game state.
 */
export function createInitialState(
  random: RandomSource = Math.random,
): AmbientGameState {
  return createLevelState(1, 0, 1, random);
}

/**
 * Returns no blockers because the active game no longer has gameplay layers.
 * @param pieces Current fish collection, retained for API compatibility.
 * @param pieceId Fish identifier, retained for API compatibility.
 * @returns An empty blocker collection.
 */
export function getBlockerIds(
  pieces: readonly PilePiece[],
  pieceId: string,
): readonly string[] {
  void pieces;
  void pieceId;
  return [];
}

/**
 * Exposes every remaining fish as directly selectable.
 * @param pieces Current fish collection.
 * @returns The same collection without layer gating.
 */
export function getSelectablePieces(
  pieces: readonly PilePiece[],
): readonly PilePiece[] {
  return pieces;
}

/**
 * Checks whether the current inventory contains a complete visible triple.
 * @param pieces Current field fish.
 * @returns Whether any species occurs at least three times.
 */
export function hasQuickMatch(pieces: readonly PilePiece[]): boolean {
  const counts = new Map<FishKind, number>();
  for (const piece of pieces) {
    counts.set(piece.kind, (counts.get(piece.kind) ?? 0) + 1);
  }
  return [...counts.values()].some((count) => count >= 3);
}

/**
 * Mirrors quick-match availability now that every fish is visible by default.
 * @param pieces Current field fish.
 * @returns Whether the field contains a complete triple.
 */
export function hasDiscoverableMatch(pieces: readonly PilePiece[]): boolean {
  return hasQuickMatch(pieces);
}
