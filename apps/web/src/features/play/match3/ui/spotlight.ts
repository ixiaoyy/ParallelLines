import {
  DISCOVERY_RADIUS_X,
  DISCOVERY_RADIUS_Y,
  INITIAL_DISCOVERY_POINT,
  type PilePiece,
  type Point,
} from "../engine";

export type SpotlightMode = "inactive" | "searching" | "afterglow" | "dragging";
export type SpotlightDirection = "up" | "right" | "down" | "left";
export const POINTER_DRAG_THRESHOLD = 7;
export const MINIMUM_FISH_TARGET_SIZE = 44;
export const MAGNETIC_FISH_RADIUS = 40;

const FISH_TARGET_GAP = MINIMUM_FISH_TARGET_SIZE + 4;
const FISH_TARGET_LAYOUT_ITERATIONS = 96;
const HINTED_SPOTLIGHT_RADIUS_SCALE = 1.35;

export interface FieldProjection {
  readonly left: number;
  readonly top: number;
  readonly width: number;
  readonly height: number;
}

export interface FieldSurfaceSize {
  readonly width: number;
  readonly height: number;
}

export interface FishTargetLayoutOptions {
  readonly pieces: readonly PilePiece[];
  readonly revealedIds: ReadonlySet<string>;
  readonly projection: FieldProjection;
  readonly surfaceSize: FieldSurfaceSize;
  readonly minimumTargetSize?: number;
}

export interface MagneticFishTarget {
  readonly id: string;
  readonly center: Point;
}

export interface FieldProjectionScheduler {
  schedule(surfaceWidth: number, surfaceHeight: number): void;
  cancel(): void;
}

type ScheduleFrame = (callback: () => void) => () => void;

export const FULL_FIELD_PROJECTION: FieldProjection = Object.freeze({
  left: 0,
  top: 0,
  width: 1,
  height: 1,
});

export const LANDSCAPE_FIELD_PROJECTION: FieldProjection = Object.freeze({
  left: 0.06,
  top: 0.02,
  width: 0.82,
  height: 0.96,
});

export const PORTRAIT_FIELD_PROJECTION: FieldProjection = Object.freeze({
  left: 0.02,
  top: 0.1,
  width: 0.68,
  height: 0.7,
});

export function getFieldProjection(
  surfaceWidth: number,
  surfaceHeight: number,
): FieldProjection {
  if (surfaceWidth <= 620 || surfaceHeight <= 620) {
    return { left: 0, top: 0, width: 1, height: 0.74 };
  }
  return surfaceWidth < surfaceHeight * 1.05
    ? PORTRAIT_FIELD_PROJECTION
    : LANDSCAPE_FIELD_PROJECTION;
}

export function createFieldProjectionScheduler(
  commit: (projection: FieldProjection) => void,
  scheduleFrame: ScheduleFrame,
): FieldProjectionScheduler {
  let latestSize: { width: number; height: number } | null = null;
  let cancelPendingFrame: (() => void) | null = null;

  function flush(): void {
    cancelPendingFrame = null;
    const size = latestSize;
    latestSize = null;
    if (!size) return;
    commit(getFieldProjection(size.width, size.height));
  }

  return {
    schedule(surfaceWidth, surfaceHeight) {
      if (
        !Number.isFinite(surfaceWidth) ||
        !Number.isFinite(surfaceHeight) ||
        surfaceWidth <= 0 ||
        surfaceHeight <= 0
      ) return;
      latestSize = { width: surfaceWidth, height: surfaceHeight };
      cancelPendingFrame ??= scheduleFrame(flush);
    },
    cancel() {
      cancelPendingFrame?.();
      cancelPendingFrame = null;
      latestSize = null;
    },
  };
}

export function projectFieldPoint(
  point: Point,
  projection: FieldProjection,
): Point {
  return {
    x: projection.left + point.x * projection.width,
    y: projection.top + point.y * projection.height,
  };
}

export function unprojectFieldPoint(
  point: Point,
  projection: FieldProjection,
): Point {
  return {
    x: Math.min(1, Math.max(0, (point.x - projection.left) / projection.width)),
    y: Math.min(1, Math.max(0, (point.y - projection.top) / projection.height)),
  };
}

/**
 * Computes transient pixel offsets that keep every revealed fish target
 * independently reachable inside the projected field without mutating its
 * canonical coordinates.
 *
 * @param options Canonical pieces, current reveal set, surface projection and
 * rendered surface size used to measure target collisions.
 * @returns A stable map of UI-only pixel offsets keyed by piece ID.
 */
export function getFishTargetOffsets({
  pieces,
  revealedIds,
  projection,
  surfaceSize,
  minimumTargetSize = MINIMUM_FISH_TARGET_SIZE,
}: FishTargetLayoutOptions): ReadonlyMap<string, Point> {
  if (
    !Number.isFinite(surfaceSize.width) ||
    !Number.isFinite(surfaceSize.height) ||
    surfaceSize.width <= 0 ||
    surfaceSize.height <= 0
  ) {
    return new Map();
  }

  const targetSize = Math.max(1, minimumTargetSize);
  const targetGap = Math.max(targetSize, FISH_TARGET_GAP);
  const halfTarget = targetSize / 2;
  const projectedLeft = projection.left * surfaceSize.width;
  const projectedRight = (projection.left + projection.width) * surfaceSize.width;
  const projectedTop = projection.top * surfaceSize.height;
  const projectedBottom = (projection.top + projection.height) * surfaceSize.height;
  const rawMinX = projectedLeft + halfTarget;
  const rawMaxX = projectedRight - halfTarget;
  const rawMinY = projectedTop + halfTarget;
  const rawMaxY = projectedBottom - halfTarget;
  const midpointX = (projectedLeft + projectedRight) / 2;
  const midpointY = (projectedTop + projectedBottom) / 2;
  const minX = rawMinX <= rawMaxX ? rawMinX : midpointX;
  const maxX = rawMinX <= rawMaxX ? rawMaxX : midpointX;
  const minY = rawMinY <= rawMaxY ? rawMinY : midpointY;
  const maxY = rawMinY <= rawMaxY ? rawMaxY : midpointY;
  const nodes = pieces
    .filter((piece) => revealedIds.has(piece.id))
    .map((piece) => {
      const projected = projectFieldPoint(piece.pile, projection);
      const canonicalX = projected.x * surfaceSize.width;
      const canonicalY = projected.y * surfaceSize.height;
      return {
        id: piece.id,
        canonicalX,
        canonicalY,
        x: Math.min(maxX, Math.max(minX, canonicalX)),
        y: Math.min(maxY, Math.max(minY, canonicalY)),
      };
    })
    .sort((first, second) => first.id.localeCompare(second.id));

  for (
    let iteration = 0;
    iteration < FISH_TARGET_LAYOUT_ITERATIONS;
    iteration += 1
  ) {
    let collisionCount = 0;
    for (let firstIndex = 0; firstIndex < nodes.length; firstIndex += 1) {
      for (
        let secondIndex = firstIndex + 1;
        secondIndex < nodes.length;
        secondIndex += 1
      ) {
        const first = nodes[firstIndex];
        const second = nodes[secondIndex];
        if (!first || !second) continue;
        const deltaX = second.x - first.x;
        const deltaY = second.y - first.y;
        const absoluteX = Math.abs(deltaX);
        const absoluteY = Math.abs(deltaY);
        if (absoluteX >= targetGap || absoluteY >= targetGap) continue;

        collisionCount += 1;
        const overlapX = targetGap - absoluteX;
        const overlapY = targetGap - absoluteY;
        const separateHorizontally = overlapX < overlapY ||
          (
            Math.abs(overlapX - overlapY) < 0.001 &&
            (firstIndex + secondIndex + iteration) % 2 === 0
          );
        if (separateHorizontally) {
          const direction = Math.abs(deltaX) > 0.001
            ? Math.sign(deltaX)
            : (firstIndex + secondIndex) % 2 === 0 ? 1 : -1;
          const movement = overlapX / 2 + 0.01;
          first.x = Math.min(
            maxX,
            Math.max(minX, first.x - direction * movement),
          );
          second.x = Math.min(
            maxX,
            Math.max(minX, second.x + direction * movement),
          );
        } else {
          const direction = Math.abs(deltaY) > 0.001
            ? Math.sign(deltaY)
            : (firstIndex + secondIndex) % 2 === 0 ? 1 : -1;
          const movement = overlapY / 2 + 0.01;
          first.y = Math.min(
            maxY,
            Math.max(minY, first.y - direction * movement),
          );
          second.y = Math.min(
            maxY,
            Math.max(minY, second.y + direction * movement),
          );
        }
      }
    }
    if (collisionCount === 0) break;
  }

  const unresolvedCollision = nodes.some((first, firstIndex) =>
    nodes.some((second, secondIndex) =>
      secondIndex > firstIndex &&
      Math.abs(first.x - second.x) < targetSize &&
      Math.abs(first.y - second.y) < targetSize
    )
  );
  if (unresolvedCollision) {
    const slots: Point[] = [];
    for (let y = minY; y <= maxY + 0.01; y += targetSize) {
      for (let x = minX; x <= maxX + 0.01; x += targetSize) {
        slots.push({ x, y });
      }
    }
    if (slots.length >= nodes.length) {
      const usedSlots = new Set<number>();
      for (const node of nodes) {
        let nearestIndex = -1;
        let nearestDistance = Number.POSITIVE_INFINITY;
        for (let slotIndex = 0; slotIndex < slots.length; slotIndex += 1) {
          if (usedSlots.has(slotIndex)) continue;
          const slot = slots[slotIndex];
          if (!slot) continue;
          const distance = Math.hypot(
            slot.x - node.canonicalX,
            slot.y - node.canonicalY,
          );
          if (distance < nearestDistance) {
            nearestIndex = slotIndex;
            nearestDistance = distance;
          }
        }
        const slot = slots[nearestIndex];
        if (!slot) continue;
        usedSlots.add(nearestIndex);
        node.x = slot.x;
        node.y = slot.y;
      }
    }
  }

  return new Map(nodes.map((node) => [
    node.id,
    {
      x: node.x - node.canonicalX,
      y: node.y - node.canonicalY,
    },
  ]));
}

export function isPointerTap(
  start: Point,
  current: Point,
  threshold = POINTER_DRAG_THRESHOLD,
): boolean {
  return Math.hypot(current.x - start.x, current.y - start.y) < threshold;
}

/**
 * Finds fish inside a scaled copy of the canonical elliptical discovery area.
 * @param pieces Canonical fish pieces to measure without mutating them.
 * @param light Current canonical spotlight point, or null when search is idle.
 * @param radiusScale Multiplier applied to both discovery radii.
 * @returns Piece IDs whose centers fall inside the scaled ellipse.
 */
function getPieceIdsWithinSpotlightRadius(
  pieces: readonly PilePiece[],
  light: Point | null,
  radiusScale: number,
): Set<string> {
  const ids = new Set<string>();
  if (!light) return ids;
  const safeScale = Math.max(0.001, radiusScale);
  for (const piece of pieces) {
    const distance = Math.hypot(
      (piece.pile.x - light.x) / (DISCOVERY_RADIUS_X * safeScale),
      (piece.pile.y - light.y) / (DISCOVERY_RADIUS_Y * safeScale),
    );
    if (distance <= 1) ids.add(piece.id);
  }
  return ids;
}

/**
 * Returns a visual-only preview ring immediately outside the reveal area.
 * @param pieces Canonical fish pieces available for transient projection.
 * @param light Current canonical spotlight point, or null when search is idle.
 * @returns IDs in the outer hint ring, excluding already revealed fish.
 */
export function getHintedPieceIds(
  pieces: readonly PilePiece[],
  light: Point | null,
): ReadonlySet<string> {
  const hintedIds = getPieceIdsWithinSpotlightRadius(
    pieces,
    light,
    HINTED_SPOTLIGHT_RADIUS_SCALE,
  );
  for (const revealedId of getPieceIdsWithinSpotlightRadius(pieces, light, 1)) {
    hintedIds.delete(revealedId);
  }
  return hintedIds;
}

export function getRevealedPieceIds(
  pieces: readonly PilePiece[],
  light: Point | null,
  retainedPieceIds: readonly (string | null)[] = [],
): ReadonlySet<string> {
  const pieceIds = new Set(pieces.map((piece) => piece.id));
  const ids = new Set(
    retainedPieceIds.filter((pieceId): pieceId is string =>
      pieceId !== null && pieceIds.has(pieceId)
    ),
  );
  if (!light) return ids;
  for (const pieceId of getPieceIdsWithinSpotlightRadius(pieces, light, 1)) {
    ids.add(pieceId);
  }
  return ids;
}

export function moveSpotlight(
  current: Point | null,
  direction: SpotlightDirection,
  fast = false,
): Point {
  const origin = current ?? INITIAL_DISCOVERY_POINT;
  const multiplier = fast ? 2 : 1;
  const movement: Readonly<Record<SpotlightDirection, Point>> = {
    up: { x: 0, y: -0.075 },
    right: { x: 0.055, y: 0 },
    down: { x: 0, y: 0.075 },
    left: { x: -0.055, y: 0 },
  };
  const delta = movement[direction];
  return {
    x: Math.min(0.94, Math.max(0.06, origin.x + delta.x * multiplier)),
    y: Math.min(0.88, Math.max(0.1, origin.y + delta.y * multiplier)),
  };
}

export function findNearestRevealedPiece(
  pieces: readonly PilePiece[],
  revealedIds: ReadonlySet<string>,
  light: Point,
): PilePiece | null {
  return [...pieces]
    .filter((piece) => revealedIds.has(piece.id))
    .sort((first, second) =>
      Math.hypot(first.pile.x - light.x, first.pile.y - light.y) -
      Math.hypot(second.pile.x - light.x, second.pile.y - light.y)
    )[0] ?? null;
}

/**
 * Resolves the closest rendered fish center inside a forgiving pointer radius.
 * @param targets Currently revealed rendered targets measured in surface pixels.
 * @param pointer Pointer position measured in the same surface pixel space.
 * @param radius Maximum center distance that may acquire a fish target.
 * @returns The winning canonical fish ID, or null when the pointer is outside all targets.
 */
export function findNearestMagneticFish(
  targets: readonly MagneticFishTarget[],
  pointer: Point,
  radius: number = MAGNETIC_FISH_RADIUS,
): string | null {
  return [...targets]
    .map((target) => ({
      ...target,
      distance: Math.hypot(
        target.center.x - pointer.x,
        target.center.y - pointer.y,
      ),
    }))
    .filter((target) => target.distance <= radius)
    .sort((first, second) =>
      first.distance - second.distance || first.id.localeCompare(second.id)
    )[0]?.id ?? null;
}
