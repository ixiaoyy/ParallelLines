import {
  FISH_KINDS,
  MAX_PIECE_COUNT,
  createInitialState,
  createLevelState,
  getLevelConfig,
  restartAfterLoss,
  type AmbientGameState,
  type FishKind,
  type PilePiece,
  type Point,
  type RandomSource,
  type TrayPiece,
} from "../engine";

export const AMBIENT_STORAGE_KEY = "parallellines.match3.ambient-state";
export const AMBIENT_SNAPSHOT_VERSION = 4;

export interface AmbientPreferences {
  readonly soundEnabled: boolean;
}

export interface AmbientPlantProgress {
  readonly plantedAt: number;
}

export interface AmbientPetProgress {
  readonly guardedPieceId: string | null;
  readonly fishFedCount: number;
}

export interface AmbientSnapshotV4 {
  readonly version: 4;
  readonly game: AmbientGameState;
  readonly preferences: AmbientPreferences;
  readonly plant: AmbientPlantProgress;
  readonly pet: AmbientPetProgress;
}

export interface AmbientSnapshotLoadResult {
  readonly snapshot: AmbientSnapshotV4;
  readonly loadedFromStorage: boolean;
}

export interface StorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

interface LegacyPilePiece {
  readonly id: string;
  readonly kind: FishKind;
  readonly pile: Point;
  readonly spread: Point;
  readonly rotation: number;
  readonly scale: number;
  readonly layer: 0 | 1 | 2;
  readonly blockerIds?: readonly string[];
}

interface LegacyTrayPiece {
  readonly id: string;
  readonly kind: FishKind;
}

interface LegacyFedFish extends LegacyTrayPiece {
  readonly settled: boolean;
}

interface LegacyGameParts {
  readonly pieces: readonly LegacyPilePiece[];
  readonly tray: readonly LegacyTrayPiece[];
  readonly fed: readonly LegacyFedFish[];
  readonly clearCount: number;
  readonly nextPieceId: number;
}

interface LegacyGame extends LegacyGameParts {
  readonly level: number;
}

const LEGACY_V2_KIND_MAP = {
  aqua: "whale",
  amber: "koi",
  lime: "sardine",
  rose: "pufferfish",
  goldfish: "goldfish",
  clownfish: "clownfish",
  angelfish: "angelfish",
  betta: "betta",
} as const satisfies Readonly<Record<string, FishKind>>;

type LegacyV2Kind = keyof typeof LEGACY_V2_KIND_MAP;
type KindParser = (value: unknown) => FishKind | null;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isSafeCounter(value: unknown, minimum: number): value is number {
  return Number.isSafeInteger(value) && (value as number) >= minimum;
}

function isFiniteInRange(
  value: unknown,
  minimum: number,
  maximum: number,
): value is number {
  return typeof value === "number" &&
    Number.isFinite(value) &&
    value >= minimum &&
    value <= maximum;
}

function parseFishKind(value: unknown): FishKind | null {
  return typeof value === "string" && FISH_KINDS.includes(value as FishKind)
    ? value as FishKind
    : null;
}

function parseLegacyV2Kind(value: unknown): FishKind | null {
  if (
    typeof value !== "string" ||
    !Object.prototype.hasOwnProperty.call(LEGACY_V2_KIND_MAP, value)
  ) {
    return null;
  }
  return LEGACY_V2_KIND_MAP[value as LegacyV2Kind];
}

function parsePoint(value: unknown): Point | null {
  if (!isRecord(value)) return null;
  if (!isFiniteInRange(value.x, 0, 1) || !isFiniteInRange(value.y, 0, 1)) {
    return null;
  }
  return { x: value.x, y: value.y };
}

/**
 * Validates optional explicit higher-layer relationships for a persisted fish.
 * @param value Unknown blocker ID collection.
 * @param pieceId ID that must not appear in its own blocker collection.
 * @returns Valid IDs, undefined when omitted, or null when invalid.
 */
function parseBlockerIds(
  value: unknown,
  pieceId: unknown,
): readonly string[] | undefined | null {
  if (value === undefined) return undefined;
  if (
    !Array.isArray(value) ||
    !value.every((id) => typeof id === "string" && id.length > 0) ||
    value.includes(pieceId) ||
    new Set(value).size !== value.length
  ) {
    return null;
  }
  return value as string[];
}

/**
 * Parses the geometry shared by current and legacy pile pieces.
 * @param value Persisted pile-piece record.
 * @returns Validated geometry, or null when any field is outside its contract.
 */
function parsePileGeometry(
  value: Record<string, unknown>,
): Omit<LegacyPilePiece, "id" | "kind"> | null {
  const pile = parsePoint(value.pile);
  const spread = parsePoint(value.spread);
  const blockerIds = parseBlockerIds(value.blockerIds, value.id);
  if (
    !pile ||
    !spread ||
    !isFiniteInRange(value.rotation, -360, 360) ||
    !isFiniteInRange(value.scale, 0.5, 1.5) ||
    (value.layer !== 0 && value.layer !== 1 && value.layer !== 2) ||
    blockerIds === null
  ) {
    return null;
  }
  return {
    pile,
    spread,
    rotation: value.rotation,
    scale: value.scale,
    layer: value.layer,
    ...(blockerIds === undefined ? {} : { blockerIds }),
  };
}

/**
 * Parses a version-four small-fish pile piece.
 * @param value Unknown persisted piece.
 * @returns A validated canonical pile piece, or null.
 */
function parsePilePiece(value: unknown): PilePiece | null {
  if (!isRecord(value)) return null;
  const kind = parseFishKind(value.kind);
  const geometry = parsePileGeometry(value);
  if (
    typeof value.id !== "string" ||
    value.id.length === 0 ||
    !kind ||
    !geometry
  ) {
    return null;
  }
  return { id: value.id, kind, ...geometry };
}

/**
 * Parses a legacy pile piece with the migration-specific species decoder.
 * @param value Unknown persisted legacy piece.
 * @param parseKind Species decoder for the source snapshot version.
 * @returns A validated legacy pile piece, or null.
 */
function parseLegacyPilePiece(
  value: unknown,
  parseKind: KindParser,
): LegacyPilePiece | null {
  if (!isRecord(value)) return null;
  const kind = parseKind(value.kind);
  const geometry = parsePileGeometry(value);
  if (
    typeof value.id !== "string" ||
    value.id.length === 0 ||
    !kind ||
    !geometry
  ) {
    return null;
  }
  return { id: value.id, kind, ...geometry };
}

/**
 * Parses a version-four small-fish tray entry.
 * @param value Unknown persisted tray value.
 * @returns A validated canonical tray piece, or null.
 */
function parseTrayPiece(value: unknown): TrayPiece | null {
  if (!isRecord(value)) return null;
  const kind = parseFishKind(value.kind);
  if (
    typeof value.id !== "string" ||
    value.id.length === 0 ||
    !kind
  ) {
    return null;
  }
  return { id: value.id, kind };
}

/**
 * Parses a legacy tray entry with the migration-specific species decoder.
 * @param value Unknown persisted legacy tray entry.
 * @param parseKind Species decoder for the source snapshot version.
 * @returns A validated legacy tray entry, or null.
 */
function parseLegacyTrayPiece(
  value: unknown,
  parseKind: KindParser,
): LegacyTrayPiece | null {
  if (!isRecord(value)) return null;
  const kind = parseKind(value.kind);
  if (typeof value.id !== "string" || value.id.length === 0 || !kind) {
    return null;
  }
  return { id: value.id, kind };
}

/**
 * Parses an obsolete feed-credit entry only for v3/v2 migration.
 * @param value Unknown persisted legacy feed entry.
 * @param parseKind Species decoder for the source snapshot version.
 * @returns A validated legacy feed entry, or null.
 */
function parseLegacyFedFish(
  value: unknown,
  parseKind: KindParser,
): LegacyFedFish | null {
  const piece = parseLegacyTrayPiece(value, parseKind);
  if (!piece || !isRecord(value) || typeof value.settled !== "boolean") {
    return null;
  }
  return { ...piece, settled: value.settled };
}

/**
 * Validates the canonical v4 game inventory and the current wave contract.
 * @param value Unknown persisted game object.
 * @returns A canonical game state, or null when any invariant fails.
 */
function parseGame(value: unknown): AmbientGameState | null {
  if (
    !isRecord(value) ||
    !Array.isArray(value.pieces) ||
    !Array.isArray(value.tray) ||
    value.pieces.length > MAX_PIECE_COUNT ||
    value.tray.length > 7 ||
    !isSafeCounter(value.level, 1) ||
    !isSafeCounter(value.clearCount, 0) ||
    !isSafeCounter(value.nextPieceId, 1)
  ) {
    return null;
  }
  const isLegacyTripleBoard = value.levelProgress === undefined;
  const levelProgress = isLegacyTripleBoard
    ? 0
    : isSafeCounter(value.levelProgress, 0)
    ? value.levelProgress
    : null;
  if (levelProgress === null) return null;

  const pieces = value.pieces.map(parsePilePiece);
  const tray = value.tray.map(parseTrayPiece);
  if (pieces.some((piece) => piece === null) || tray.some((piece) => piece === null)) {
    return null;
  }
  const parsedPieces = pieces.filter((piece): piece is PilePiece => piece !== null);
  const parsedTray = tray.filter((piece): piece is TrayPiece => piece !== null);
  const inventory = [...parsedPieces, ...parsedTray];
  const ids = inventory.map((piece) => piece.id);
  const config = getLevelConfig(value.level);
  const maximum = isLegacyTripleBoard
    ? MAX_PIECE_COUNT
    : config.pieceCount;
  if (
    new Set(ids).size !== ids.length ||
    inventory.length === 0 ||
    inventory.length > maximum ||
    levelProgress >= config.targetCount
  ) {
    return null;
  }

  const kindCounts = FISH_KINDS.map((kind) =>
    inventory.filter((piece) => piece.kind === kind).length
  ).filter((count) => count > 0);
  if (isLegacyTripleBoard) {
    if (
      inventory.length % 3 !== 0 ||
      kindCounts.some((count) => count % 3 !== 0)
    ) {
      return null;
    }
  } else if (value.level === 1) {
    if (
      inventory.length !== (config.targetCount - levelProgress) * 3 ||
      kindCounts.some((count) => count !== 3)
    ) {
      return null;
    }
  } else if (
    inventory.length !== config.pieceCount ||
    kindCounts.length !== config.kindCount ||
    kindCounts.filter((count) => count === 3).length !== 1 ||
    kindCounts.some((count) => count !== 2 && count !== 3)
  ) {
    return null;
  }

  return {
    pieces: parsedPieces,
    tray: parsedTray,
    clearCount: value.clearCount,
    level: value.level,
    levelProgress,
    nextPieceId: value.nextPieceId,
  };
}

/**
 * Validates the shared v1-v3 inventory shell before version-specific migration.
 * @param value Unknown persisted legacy game value.
 * @param parseKind Species decoder for the source snapshot version.
 * @param allowMissingFed Whether the older schema may omit its feed collection.
 * @returns Validated legacy inventory parts, or null.
 */
function parseLegacyGameParts(
  value: unknown,
  parseKind: KindParser,
  allowMissingFed = false,
): LegacyGameParts | null {
  if (
    !isRecord(value) ||
    !Array.isArray(value.pieces) ||
    !Array.isArray(value.tray) ||
    (!allowMissingFed && !Array.isArray(value.fed)) ||
    (value.fed !== undefined && !Array.isArray(value.fed))
  ) {
    return null;
  }
  const rawFed = Array.isArray(value.fed) ? value.fed : [];
  if (
    value.pieces.length > MAX_PIECE_COUNT ||
    value.tray.length > 7 ||
    rawFed.length > 3
  ) {
    return null;
  }

  const pieces = value.pieces.map((piece) => parseLegacyPilePiece(piece, parseKind));
  const tray = value.tray.map((piece) => parseLegacyTrayPiece(piece, parseKind));
  const fed = rawFed.map((piece) => parseLegacyFedFish(piece, parseKind));
  if (
    pieces.some((piece) => piece === null) ||
    tray.some((piece) => piece === null) ||
    fed.some((piece) => piece === null) ||
    !isSafeCounter(value.clearCount, 0) ||
    !isSafeCounter(value.nextPieceId, 1)
  ) {
    return null;
  }
  const parsedPieces = pieces.filter(
    (piece): piece is LegacyPilePiece => piece !== null,
  );
  const parsedTray = tray.filter(
    (piece): piece is LegacyTrayPiece => piece !== null,
  );
  const parsedFed = fed.filter((piece): piece is LegacyFedFish => piece !== null);
  const ids = [
    ...parsedPieces.map((piece) => piece.id),
    ...parsedTray.map((piece) => piece.id),
    ...parsedFed.map((piece) => piece.id),
  ];
  if (new Set(ids).size !== ids.length) return null;
  return {
    pieces: parsedPieces,
    tray: parsedTray,
    fed: parsedFed,
    clearCount: value.clearCount,
    nextPieceId: value.nextPieceId,
  };
}

/**
 * Validates a finite v2/v3 game including obsolete unsettled feed credits.
 * @param value Unknown persisted legacy game value.
 * @param parseKind Species decoder for the source snapshot version.
 * @param allowMissingFed Whether the older schema may omit its feed collection.
 * @returns A validated legacy finite game, or null.
 */
function parseLegacyGame(
  value: unknown,
  parseKind: KindParser,
  allowMissingFed = false,
): LegacyGame | null {
  if (!isRecord(value) || !isSafeCounter(value.level, 1)) return null;
  const parts = parseLegacyGameParts(value, parseKind, allowMissingFed);
  if (!parts) return null;
  const unsettledFed = parts.fed.filter((piece) => !piece.settled);
  const inventory = [...parts.pieces, ...parts.tray, ...unsettledFed];
  const recordedTotal = parts.pieces.length + parts.tray.length + parts.fed.length;
  const maximum = MAX_PIECE_COUNT;
  if (
    inventory.length === 0 ||
    inventory.length > maximum ||
    recordedTotal > maximum ||
    inventory.length % 3 !== 0
  ) {
    return null;
  }
  for (const kind of FISH_KINDS) {
    if (inventory.filter((piece) => piece.kind === kind).length % 3 !== 0) {
      return null;
    }
  }
  return { ...parts, level: value.level };
}

function parsePlant(value: unknown, now: number): AmbientPlantProgress | null {
  if (value === undefined) return { plantedAt: now };
  if (!isRecord(value) || !isSafeCounter(value.plantedAt, 0)) return null;
  return { plantedAt: value.plantedAt };
}

function parsePreferences(value: unknown): AmbientPreferences | null {
  if (!isRecord(value) || typeof value.soundEnabled !== "boolean") return null;
  return { soundEnabled: value.soundEnabled };
}

function parsePet(
  value: unknown,
  game: AmbientGameState,
): AmbientPetProgress | null {
  if (!isRecord(value) || !isSafeCounter(value.fishFedCount, 0)) return null;
  const guardedPieceId = typeof value.guardedPieceId === "string" &&
      game.pieces.some((piece) => piece.id === value.guardedPieceId)
    ? value.guardedPieceId
    : null;
  return { guardedPieceId, fishFedCount: value.fishFedCount };
}

/**
 * Parses only the current version-four snapshot schema.
 * @param value Unknown persisted root value.
 * @param now Timestamp used only when the optional plant field is absent.
 * @returns A validated snapshot, or null when the schema is incompatible.
 */
export function parseAmbientSnapshot(
  value: unknown,
  now = Date.now(),
): AmbientSnapshotV4 | null {
  if (!isRecord(value) || value.version !== AMBIENT_SNAPSHOT_VERSION) return null;
  const game = parseGame(value.game);
  const preferences = parsePreferences(value.preferences);
  const plant = parsePlant(value.plant, now);
  if (!game || !preferences || !plant) return null;
  const pet = parsePet(value.pet, game);
  if (!pet) return null;
  return {
    version: AMBIENT_SNAPSHOT_VERSION,
    game,
    preferences,
    plant,
    pet,
  };
}

/**
 * Rebuilds an incompatible legacy board while preserving durable progress.
 * @param game Validated legacy game that may contain obsolete feed credits.
 * @param preferences Durable sound preference.
 * @param plant Durable plant timestamp.
 * @param random Random source for the replacement small-fish level.
 * @returns A canonical version-four snapshot.
 */
function migrateLegacyGame(
  game: LegacyGame,
  preferences: AmbientPreferences,
  plant: AmbientPlantProgress,
  random: RandomSource,
): AmbientSnapshotV4 {
  return {
    version: AMBIENT_SNAPSHOT_VERSION,
    game: createLevelState(
      game.level,
      game.clearCount,
      game.nextPieceId,
      random,
    ),
    preferences,
    plant,
    pet: {
      guardedPieceId: null,
      fishFedCount: game.fed.length,
    },
  };
}

/**
 * Migrates the former canonical version-three feed-credit snapshot.
 * @param value Unknown persisted root value.
 * @param random Random source for the replacement small-fish level.
 * @param now Timestamp used when legacy plant progress is absent.
 * @returns A canonical version-four snapshot, or null.
 */
function migrateLegacyV3Snapshot(
  value: unknown,
  random: RandomSource,
  now: number,
): AmbientSnapshotV4 | null {
  if (!isRecord(value) || value.version !== 3) return null;
  const game = parseLegacyGame(value.game, parseFishKind);
  const preferences = parsePreferences(value.preferences);
  const plant = parsePlant(value.plant, now);
  if (!game || !preferences || !plant) return null;
  return migrateLegacyGame(game, preferences, plant, random);
}

function migrateLegacyV2Snapshot(
  value: unknown,
  random: RandomSource,
  now: number,
): AmbientSnapshotV4 | null {
  if (!isRecord(value) || value.version !== 2) return null;
  const game = parseLegacyGame(value.game, parseLegacyV2Kind, true);
  const preferences = parsePreferences(value.preferences);
  const plant = parsePlant(value.plant, now);
  if (!game || !preferences || !plant) return null;
  return migrateLegacyGame(game, preferences, plant, random);
}

function migrateLegacyV1Snapshot(
  value: unknown,
  random: RandomSource,
  now: number,
): AmbientSnapshotV4 | null {
  if (!isRecord(value) || value.version !== 1) return null;
  const legacyGame = parseLegacyGameParts(value.game, parseLegacyV2Kind, true);
  const preferences = parsePreferences(value.preferences);
  const plant = parsePlant(value.plant, now);
  if (!legacyGame || !preferences || !plant) return null;
  if (
    legacyGame.pieces.length + legacyGame.tray.length !== 18 ||
    legacyGame.fed.length !== 0
  ) {
    return null;
  }
  return {
    version: AMBIENT_SNAPSHOT_VERSION,
    game: createLevelState(
      1,
      legacyGame.clearCount,
      legacyGame.nextPieceId,
      random,
    ),
    preferences,
    plant,
    pet: { guardedPieceId: null, fishFedCount: 0 },
  };
}

export function createFreshSnapshot(
  random: RandomSource = Math.random,
  now = Date.now(),
): AmbientSnapshotV4 {
  return {
    version: AMBIENT_SNAPSHOT_VERSION,
    game: createInitialState(random),
    preferences: { soundEnabled: false },
    plant: { plantedAt: now },
    pet: { guardedPieceId: null, fishFedCount: 0 },
  };
}

function normalizeLoadedSnapshot(
  snapshot: AmbientSnapshotV4,
  random: RandomSource,
): AmbientSnapshotV4 {
  if (snapshot.game.tray.length < 7) return snapshot;
  return {
    ...snapshot,
    game: restartAfterLoss(snapshot.game, random),
    pet: { ...snapshot.pet, guardedPieceId: null },
  };
}

export function loadAmbientSnapshotResult(
  storage: StorageLike | null,
  random: RandomSource = Math.random,
  now = Date.now(),
): AmbientSnapshotLoadResult {
  if (!storage) {
    return {
      snapshot: createFreshSnapshot(random, now),
      loadedFromStorage: false,
    };
  }
  try {
    const raw = storage.getItem(AMBIENT_STORAGE_KEY);
    if (!raw) {
      return {
        snapshot: createFreshSnapshot(random, now),
        loadedFromStorage: false,
      };
    }
    const parsed = JSON.parse(raw) as unknown;
    const snapshot = parseAmbientSnapshot(parsed, now) ??
      migrateLegacyV3Snapshot(parsed, random, now) ??
      migrateLegacyV2Snapshot(parsed, random, now) ??
      migrateLegacyV1Snapshot(parsed, random, now);
    if (!snapshot) {
      return {
        snapshot: createFreshSnapshot(random, now),
        loadedFromStorage: false,
      };
    }
    return {
      snapshot: normalizeLoadedSnapshot(snapshot, random),
      loadedFromStorage: true,
    };
  } catch {
    return {
      snapshot: createFreshSnapshot(random, now),
      loadedFromStorage: false,
    };
  }
}

export function loadAmbientSnapshot(
  storage: StorageLike | null,
  random: RandomSource = Math.random,
  now = Date.now(),
): AmbientSnapshotV4 {
  return loadAmbientSnapshotResult(storage, random, now).snapshot;
}

export function saveAmbientSnapshot(
  storage: StorageLike | null,
  snapshot: AmbientSnapshotV4,
): boolean {
  if (!storage) return false;
  try {
    storage.setItem(AMBIENT_STORAGE_KEY, JSON.stringify(snapshot));
    return true;
  } catch {
    return false;
  }
}

export function resolveBrowserStorage(): StorageLike | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}
