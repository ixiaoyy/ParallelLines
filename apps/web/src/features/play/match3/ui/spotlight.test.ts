import { describe, expect, it } from "vitest";

import {
  DISCOVERY_RADIUS_X,
  type PilePiece,
} from "../engine";
import {
  FULL_FIELD_PROJECTION,
  LANDSCAPE_FIELD_PROJECTION,
  PORTRAIT_FIELD_PROJECTION,
  createFieldProjectionScheduler,
  findNearestMagneticFish,
  findNearestRevealedPiece,
  getFieldProjection,
  getFishTargetOffsets,
  getHintedPieceIds,
  getRevealedPieceIds,
  isPointerTap,
  MINIMUM_FISH_TARGET_SIZE,
  moveSpotlight,
  projectFieldPoint,
  unprojectFieldPoint,
  type FieldProjection,
} from "./spotlight";

const pieces: readonly PilePiece[] = [
  {
    id: "near",
    kind: "whale",
    pile: { x: 0.5, y: 0.5 },
    spread: { x: 0.5, y: 0.5 },
    rotation: 0,
    scale: 1,
    layer: 0,
  },
  {
    id: "far",
    kind: "koi",
    pile: { x: 0.85, y: 0.8 },
    spread: { x: 0.85, y: 0.8 },
    rotation: 0,
    scale: 1,
    layer: 0,
  },
];

describe("spotlight projection", () => {
  it("reveals only local fish while retaining active semantic and drag targets", () => {
    expect([...getRevealedPieceIds(
      pieces,
      { x: 0.5, y: 0.5 },
      ["far", "missing"],
    )]).toEqual([
      "far",
      "near",
    ]);
    expect(getRevealedPieceIds(pieces, null).size).toBe(0);
  });

  it("keeps a focused fish revealed when the light moves away", () => {
    expect(getRevealedPieceIds(
      pieces,
      { x: 0.85, y: 0.8 },
      ["near"],
    )).toEqual(new Set(["near", "far"]));
  });

  it("retains only the exact guided fish when no pointer light is active", () => {
    expect(getRevealedPieceIds(pieces, null, ["near"])).toEqual(
      new Set(["near"]),
    );
  });

  it("previews only fish in the non-interactive ring outside reveal range", () => {
    const light = { x: 0.5, y: 0.5 };
    const ringPieces: readonly PilePiece[] = [
      {
        ...pieces[0],
        id: "revealed",
        pile: { x: light.x + DISCOVERY_RADIUS_X * 0.9, y: light.y },
      },
      {
        ...pieces[0],
        id: "hinted",
        pile: { x: light.x + DISCOVERY_RADIUS_X * 1.2, y: light.y },
      },
      {
        ...pieces[0],
        id: "hidden",
        pile: { x: light.x + DISCOVERY_RADIUS_X * 1.4, y: light.y },
      },
    ];

    expect(getHintedPieceIds(ringPieces, light)).toEqual(new Set(["hinted"]));
    expect(getHintedPieceIds(ringPieces, null).size).toBe(0);
    expect(getRevealedPieceIds(ringPieces, light)).toEqual(
      new Set(["revealed"]),
    );
  });

  it("distinguishes a tap from a drag using the shared movement threshold", () => {
    expect(isPointerTap({ x: 10, y: 10 }, { x: 14, y: 14 })).toBe(true);
    expect(isPointerTap({ x: 10, y: 10 }, { x: 17, y: 10 })).toBe(false);
  });

  it("moves and clamps the keyboard light", () => {
    expect(moveSpotlight({ x: 0.93, y: 0.11 }, "right", true).x).toBe(0.94);
    expect(moveSpotlight({ x: 0.93, y: 0.11 }, "up", true).y).toBe(0.1);
  });

  it("chooses the closest revealed semantic target", () => {
    expect(findNearestRevealedPiece(
      pieces,
      new Set(["near", "far"]),
      { x: 0.52, y: 0.52 },
    )?.id).toBe("near");
  });

  it("magnetically acquires the closest rendered fish with stable ties", () => {
    const targets = [
      { id: "fish-b", center: { x: 70, y: 50 } },
      { id: "fish-a", center: { x: 30, y: 50 } },
      { id: "fish-far", center: { x: 140, y: 50 } },
    ];

    expect(findNearestMagneticFish(targets, { x: 52, y: 50 }, 40))
      .toBe("fish-b");
    expect(findNearestMagneticFish(targets, { x: 50, y: 50 }, 40))
      .toBe("fish-a");
    expect(findNearestMagneticFish(targets, { x: 100, y: 120 }, 40))
      .toBeNull();
  });

  it("fans crowded fish into stable independent 44px targets", () => {
    const crowded = Array.from({ length: 6 }, (_, index): PilePiece => ({
      id: `crowded-${index}`,
      kind: index % 2 === 0 ? "whale" : "koi",
      pile: { x: 0.46 + index * 0.008, y: 0.38 + index * 0.004 },
      spread: { x: 0.46 + index * 0.008, y: 0.38 + index * 0.004 },
      rotation: index * 35,
      scale: 0.92 + index * 0.01,
      layer: index % 2 as 0 | 1,
    }));
    const canonical = JSON.stringify(crowded);
    const projection = getFieldProjection(320, 568);
    const revealedIds = new Set(crowded.map((piece) => piece.id));
    const offsets = getFishTargetOffsets({
      pieces: crowded,
      revealedIds,
      projection,
      surfaceSize: { width: 320, height: 568 },
    });
    const reversedOffsets = getFishTargetOffsets({
      pieces: [...crowded].reverse(),
      revealedIds,
      projection,
      surfaceSize: { width: 320, height: 568 },
    });
    const centers = crowded.map((piece) => {
      const projected = projectFieldPoint(piece.pile, projection);
      const offset = offsets.get(piece.id) ?? { x: 0, y: 0 };
      return {
        id: piece.id,
        x: projected.x * 320 + offset.x,
        y: projected.y * 568 + offset.y,
      };
    });

    for (let firstIndex = 0; firstIndex < centers.length; firstIndex += 1) {
      for (
        let secondIndex = firstIndex + 1;
        secondIndex < centers.length;
        secondIndex += 1
      ) {
        const first = centers[firstIndex];
        const second = centers[secondIndex];
        if (!first || !second) continue;
        expect(
          Math.abs(first.x - second.x) >= MINIMUM_FISH_TARGET_SIZE ||
            Math.abs(first.y - second.y) >= MINIMUM_FISH_TARGET_SIZE,
        ).toBe(true);
      }
    }
    expect([...reversedOffsets.entries()]).toEqual([...offsets.entries()]);
    expect(JSON.stringify(crowded)).toBe(canonical);
  });

  it("keeps fanned target cores inside compact projected bounds", () => {
    const edgePieces = Array.from({ length: 4 }, (_, index): PilePiece => ({
      id: `edge-${index}`,
      kind: "sardine",
      pile: { x: 0.01, y: 0.01 },
      spread: { x: 0.01, y: 0.01 },
      rotation: 0,
      scale: 1,
      layer: index % 2 as 0 | 1,
    }));
    const projection = getFieldProjection(320, 240);
    const offsets = getFishTargetOffsets({
      pieces: edgePieces,
      revealedIds: new Set(edgePieces.map((piece) => piece.id)),
      projection,
      surfaceSize: { width: 320, height: 240 },
    });
    const halfTarget = MINIMUM_FISH_TARGET_SIZE / 2;

    for (const piece of edgePieces) {
      const projected = projectFieldPoint(piece.pile, projection);
      const offset = offsets.get(piece.id) ?? { x: 0, y: 0 };
      const x = projected.x * 320 + offset.x;
      const y = projected.y * 240 + offset.y;
      expect(x).toBeGreaterThanOrEqual(halfTarget);
      expect(x).toBeLessThanOrEqual(320 - halfTarget);
      expect(y).toBeGreaterThanOrEqual(halfTarget);
      expect(y).toBeLessThanOrEqual(projection.height * 240 - halfTarget);
    }
  });

  it("reprojects compact surfaces without changing canonical coordinates", () => {
    expect(getFieldProjection(1440, 900)).toBe(LANDSCAPE_FIELD_PROJECTION);
    expect(getFieldProjection(900, 1200)).toBe(PORTRAIT_FIELD_PROJECTION);
    expect(FULL_FIELD_PROJECTION).toEqual({ left: 0, top: 0, width: 1, height: 1 });
    const compact = getFieldProjection(320, 568);
    const canonical = { x: 0.23, y: 0.66 };
    const projected = projectFieldPoint(canonical, compact);

    expect(projected.x).toBeCloseTo(0.23);
    expect(projected.y).toBeCloseTo(0.4884);
    const restored = unprojectFieldPoint(projected, compact);
    expect(restored.x).toBeCloseTo(canonical.x);
    expect(restored.y).toBeCloseTo(canonical.y);
  });

  it("spreads the authored school across the left landscape scene", () => {
    const topLeft = projectFieldPoint({ x: 0.12, y: 0.12 },
      LANDSCAPE_FIELD_PROJECTION);
    const bottomRight = projectFieldPoint({ x: 0.63, y: 0.71 },
      LANDSCAPE_FIELD_PROJECTION);

    expect(topLeft.x).toBeCloseTo(0.1584);
    expect(topLeft.y).toBeCloseTo(0.1352);
    expect(bottomRight.x).toBeCloseTo(0.5766);
    expect(bottomRight.y).toBeCloseTo(0.7016);
  });

  it("coalesces resize projection commits and cancels pending work", () => {
    const frames = new Map<number, () => void>();
    const cancelled: number[] = [];
    const projections: FieldProjection[] = [];
    let nextFrameId = 1;
    const scheduler = createFieldProjectionScheduler(
      (projection) => projections.push(projection),
      (callback) => {
        const frameId = nextFrameId;
        nextFrameId += 1;
        frames.set(frameId, callback);
        return () => {
          cancelled.push(frameId);
          frames.delete(frameId);
        };
      },
    );

    scheduler.schedule(320, 568);
    scheduler.schedule(430, 560);
    scheduler.schedule(Number.NaN, 240);

    expect(frames.size).toBe(1);
    expect(projections).toEqual([]);
    frames.get(1)?.();
    frames.delete(1);
    expect(projections).toEqual([getFieldProjection(430, 560)]);

    scheduler.schedule(320, 240);
    expect(frames.size).toBe(1);
    scheduler.cancel();
    expect(frames.size).toBe(0);
    expect(cancelled).toEqual([2]);
    expect(projections).toHaveLength(1);
  });
});
