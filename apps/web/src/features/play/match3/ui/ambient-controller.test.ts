import { describe, expect, it, vi } from "vitest";

import {
  FISH_KINDS,
  createInitialState,
  createLevelState,
  createSeededRandom,
  type AmbientGameState,
  type PilePiece,
} from "../engine";
import {
  AMBIENT_STORAGE_KEY,
  createFreshSnapshot,
  saveAmbientSnapshot,
  type StorageLike,
} from "../session/ambient-storage";
import {
  createAmbientController,
  getCatBondStage,
  type TimerApi,
} from "./ambient-controller";
import {
  CAT_CURIOUS_DURATION,
  CAT_PET_DURATION,
  CAT_PLAY_DURATION,
  FISH_CATCH_FLIGHT_DURATION,
  FISH_FEED_SETTLE_DURATION,
  FISH_MERGE_CONTACT_DURATION,
} from "./game-ui";

interface MemoryStorage extends StorageLike {
  readonly values: Map<string, string>;
}

/**
 * Creates deterministic in-memory local storage for controller persistence tests.
 * @returns A storage adapter whose serialized values remain inspectable.
 */
function memoryStorage(): MemoryStorage {
  const values = new Map<string, string>();
  return {
    values,
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
  };
}

/**
 * Creates a timer harness that can run one scheduled delay at a time.
 * @returns Timer API plus pending callbacks, delays, and a delay runner.
 */
function controlledTimers() {
  const callbacks: Array<() => void> = [];
  const delays: number[] = [];
  const timers: TimerApi = {
    schedule(callback, delay) {
      callbacks.push(callback);
      delays.push(delay);
      return callback;
    },
    cancel(handle) {
      const index = callbacks.indexOf(handle as () => void);
      if (index < 0) return;
      callbacks.splice(index, 1);
      delays.splice(index, 1);
    },
  };

  /** Runs and removes the first pending callback with the requested delay. */
  function runDelay(delay: number): void {
    const index = delays.indexOf(delay);
    if (index < 0) return;
    const [callback] = callbacks.splice(index, 1);
    delays.splice(index, 1);
    callback?.();
  }

  /**
   * Advances one completed fish through catch and merge into cat contact.
   * @returns Nothing; the harness runs the two ordered controller callbacks.
   */
  function advanceCompletedFishToFeeding(): void {
    runDelay(FISH_CATCH_FLIGHT_DURATION);
    runDelay(FISH_MERGE_CONTACT_DURATION);
  }

  /**
   * Completes one staged fish presentation after its canonical selection.
   * @param levelAdvanced Whether the feeding phase owns the longer level cue.
   * @returns Nothing; the completed-fish controller event is fully settled.
   */
  function finishCompletedFish(levelAdvanced = false): void {
    advanceCompletedFishToFeeding();
    runDelay(levelAdvanced ? 960 : FISH_FEED_SETTLE_DURATION);
  }

  return {
    advanceCompletedFishToFeeding,
    callbacks,
    delays,
    finishCompletedFish,
    runDelay,
    timers,
  };
}

/**
 * Finds the next same-species triple available in a controller-owned pile.
 * @param game Current canonical game state.
 * @returns Three same-species fish, or null when no triple remains.
 */
function findTriple(
  game: AmbientGameState,
): readonly [PilePiece, PilePiece, PilePiece] | null {
  for (const kind of FISH_KINDS) {
    const [first, second, third] = game.pieces.filter((piece) =>
      piece.kind === kind
    );
    if (first && second && third) return [first, second, third];
  }
  return null;
}

describe("ambient controller", () => {
  it("creates one playable field when storage is absent or malformed", () => {
    const invalidStorage = memoryStorage();
    invalidStorage.setItem(AMBIENT_STORAGE_KEY, "not-json");

    for (const storage of [null, memoryStorage(), invalidStorage] as const) {
      const expected = createInitialState(createSeededRandom(38));
      const controller = createAmbientController({
        random: createSeededRandom(38),
        storage,
      });

      expect(controller.game.value).toEqual(expected);
      expect(controller.fishFedCount.value).toBe(0);
      expect(controller.bondStage.value).toBe("newcomer");
      controller.dispose();
    }
  });

  it("runs a non-blocking intro and cancels it on player takeover", () => {
    const harness = controlledTimers();
    const controller = createAmbientController({
      random: createSeededRandom(40),
      storage: null,
      timers: harness.timers,
    });

    expect(controller.feedback.value).toBe("intro");
    expect(controller.introPhase.value).toBe("scan");
    expect(controller.introTargetIds.value).toHaveLength(3);
    expect(controller.canSelect.value).toBe(true);

    harness.runDelay(520);
    expect(controller.introPhase.value).toBe("targets");
    harness.runDelay(620);
    expect(controller.introPhase.value).toBe("tray");

    controller.takeOverIntro();
    expect(controller.feedback.value).toBe("idle");
    expect(controller.introPhase.value).toBe("idle");
    expect(harness.callbacks).toHaveLength(0);
    controller.dispose();
  });

  it("persists a combination before its staged catch and feed feedback", () => {
    const storage = memoryStorage();
    const harness = controlledTimers();
    const onClear = vi.fn();
    const controller = createAmbientController({
      random: createSeededRandom(51),
      storage,
      timers: harness.timers,
      onClear,
    });
    const triple = findTriple(controller.game.value);
    expect(triple).not.toBeNull();
    if (!triple) return;

    controller.activate(triple[0].id);
    controller.activate(triple[1].id);
    controller.activate(triple[2].id);

    expect(controller.feedback.value).toBe("select");
    expect(controller.completedFish.value).toMatchObject({
      kind: triple[0].kind,
      feedCount: 1,
      phase: "catching",
    });
    expect(controller.completedFish.value?.combined.map((piece) => piece.id))
      .toEqual(triple.map((piece) => piece.id));
    expect(controller.trayPreview.value).toHaveLength(3);
    expect(controller.game.value.tray).toEqual([]);
    expect(controller.game.value.clearCount).toBe(1);
    expect(controller.fishFedCount.value).toBe(1);
    expect(controller.presentedClearCount.value).toBe(0);
    expect(controller.catPose.value).toBe("idle");
    expect(controller.catMotion.value).toBe("idle");
    expect(controller.canSelect.value).toBe(false);
    expect(onClear).not.toHaveBeenCalled();

    const persisted = JSON.parse(
      storage.values.get(AMBIENT_STORAGE_KEY) ?? "null",
    ) as { pet?: { fishFedCount?: number } };
    expect(persisted.pet?.fishFedCount).toBe(1);

    harness.runDelay(FISH_CATCH_FLIGHT_DURATION);
    expect(controller.completedFish.value?.phase).toBe("merging");
    expect(controller.catPose.value).toBe("idle");
    expect(onClear).not.toHaveBeenCalled();

    harness.runDelay(FISH_MERGE_CONTACT_DURATION);
    expect(controller.completedFish.value?.phase).toBe("feeding");
    expect(controller.feedback.value).toBe("clear");
    expect(controller.presentedClearCount.value).toBe(1);
    expect(controller.catPose.value).toBe("eating");
    expect(controller.catMotion.value).toBe("feeding");
    expect(onClear).toHaveBeenCalledOnce();

    harness.runDelay(FISH_FEED_SETTLE_DURATION);
    expect(controller.completedFish.value).toBeNull();
    expect(controller.trayPreview.value).toBeNull();
    expect(controller.canSelect.value).toBe(true);
    controller.dispose();
  });

  it("accepts unlimited later fish and derives all three bond stages", () => {
    const harness = controlledTimers();
    const controller = createAmbientController({
      random: createSeededRandom(61),
      storage: null,
      timers: harness.timers,
    });

    for (let count = 1; count <= 10; count += 1) {
      const previousLevel = controller.game.value.level;
      const triple = findTriple(controller.game.value);
      expect(triple, `feed ${count} has a triple`).not.toBeNull();
      if (!triple) return;
      for (const piece of triple) controller.activate(piece.id);
      expect(controller.fishFedCount.value).toBe(count);
      expect(controller.completedFish.value?.feedCount).toBe(count);
      harness.finishCompletedFish(controller.game.value.level > previousLevel);
    }

    expect(controller.fishFedCount.value).toBe(10);
    expect(controller.bondStage.value).toBe("bonded");
    expect(getCatBondStage(0)).toBe("newcomer");
    expect(getCatBondStage(2)).toBe("newcomer");
    expect(getCatBondStage(3)).toBe("familiar");
    expect(getCatBondStage(8)).toBe("familiar");
    expect(getCatBondStage(9)).toBe("bonded");
    controller.dispose();
  });

  it("plays a temporary full, lying, sleeping, and wake sequence every third fish", () => {
    const harness = controlledTimers();
    const controller = createAmbientController({
      random: createSeededRandom(71),
      storage: null,
      timers: harness.timers,
    });

    for (let count = 1; count <= 3; count += 1) {
      const previousLevel = controller.game.value.level;
      const triple = findTriple(controller.game.value);
      expect(triple).not.toBeNull();
      if (!triple) return;
      for (const piece of triple) controller.activate(piece.id);
      harness.finishCompletedFish(controller.game.value.level > previousLevel);
    }

    expect(controller.fishFedCount.value).toBe(3);
    expect(controller.catPose.value).toBe("eating");
    harness.runDelay(520);
    expect(controller.catPose.value).toBe("full");
    expect(controller.catMotion.value).toBe("resting");
    harness.runDelay(520);
    expect(controller.catPose.value).toBe("lying");
    harness.runDelay(520);
    expect(controller.catPose.value).toBe("sleeping");
    expect(controller.catMotion.value).toBe("sleeping");
    harness.runDelay(720);
    expect(controller.catPose.value).toBe("idle");
    expect(controller.catMotion.value).toBe("idle");
    expect(controller.canSelect.value).toBe(true);
    controller.dispose();
  });

  it("lets a later combination interrupt rest without rejecting the feed", () => {
    const harness = controlledTimers();
    const controller = createAmbientController({
      random: createSeededRandom(72),
      storage: null,
      timers: harness.timers,
    });

    for (let count = 1; count <= 3; count += 1) {
      const previousLevel = controller.game.value.level;
      const triple = findTriple(controller.game.value);
      expect(triple).not.toBeNull();
      if (!triple) return;
      for (const piece of triple) controller.activate(piece.id);
      harness.finishCompletedFish(controller.game.value.level > previousLevel);
    }
    harness.runDelay(520);
    expect(controller.catPose.value).toBe("full");

    const fourth = findTriple(controller.game.value);
    expect(fourth).not.toBeNull();
    if (!fourth) return;
    for (const piece of fourth) controller.activate(piece.id);

    expect(controller.fishFedCount.value).toBe(4);
    expect(controller.completedFish.value?.phase).toBe("catching");
    expect(controller.catPose.value).toBe("full");
    harness.advanceCompletedFishToFeeding();
    expect(controller.catPose.value).toBe("eating");
    expect(controller.catMotion.value).toBe("feeding");
    controller.dispose();
  });

  it("responds differently to each pet zone without changing progress", () => {
    const setItem = vi.fn();
    const harness = controlledTimers();
    const controller = createAmbientController({
      random: createSeededRandom(81),
      reactionRandom: () => 0,
      storage: { getItem: () => null, setItem },
      timers: harness.timers,
    });
    const gameBefore = controller.game.value;

    controller.petCat("head");
    expect(controller.catPetZone.value).toBe("head");
    expect(controller.catPose.value).toBe("idle");
    expect(controller.catMotion.value).toBe("petting");
    expect(controller.catReaction.value?.text).toBe("呼噜～");

    harness.runDelay(CAT_PET_DURATION);
    controller.petCat("belly");
    expect(controller.catPetZone.value).toBe("belly");
    expect(controller.catPose.value).toBe("sitting");
    expect(controller.catReaction.value?.text).toBe("痒痒的！");

    harness.runDelay(CAT_PET_DURATION);
    controller.petCat("paws");
    expect(controller.catPetZone.value).toBe("paws");
    expect(controller.catPose.value).toBe("excited");
    expect(controller.catReaction.value?.text).toBe("碰个爪");
    expect(controller.game.value).toBe(gameBefore);
    expect(controller.fishFedCount.value).toBe(0);
    expect(setItem).not.toHaveBeenCalled();
    controller.dispose();
  });

  it("plays with the yarn without changing or persisting progress", () => {
    const setItem = vi.fn();
    const harness = controlledTimers();
    const controller = createAmbientController({
      random: createSeededRandom(92),
      reactionRandom: () => 0,
      storage: { getItem: () => null, setItem },
      timers: harness.timers,
    });
    const gameBefore = controller.game.value;

    controller.playWithCat();

    expect(controller.catPlayVariant.value).toBe("pounce");
    expect(controller.catPose.value).toBe("idle");
    expect(controller.catMotion.value).toBe("playing");
    expect(controller.catReaction.value?.text).toBe("抓到啦");

    harness.runDelay(CAT_PLAY_DURATION);
    controller.playWithCat();
    expect(controller.catPlayVariant.value).toBe("bat");
    expect(controller.catPose.value).toBe("excited");
    expect(controller.catReaction.value?.text).toBe("飞起来啦");

    harness.runDelay(CAT_PLAY_DURATION);
    controller.playWithCat();
    expect(controller.catPlayVariant.value).toBe("cuddle");
    expect(controller.catPose.value).toBe("cuddling");
    expect(controller.catReaction.value?.text).toBe("抱住了");
    expect(controller.game.value).toBe(gameBefore);
    expect(controller.fishFedCount.value).toBe(0);
    expect(setItem).not.toHaveBeenCalled();
    harness.runDelay(CAT_PLAY_DURATION);
    expect(controller.catMotion.value).toBe("idle");
    controller.dispose();
  });

  it("adds a bounded curious pose to low-frequency idle reactions", () => {
    const harness = controlledTimers();
    const controller = createAmbientController({
      random: createSeededRandom(96),
      reactionRandom: () => 0,
      storage: null,
      timers: harness.timers,
    });

    controller.startReactions();
    harness.runDelay(45_000);

    expect(controller.catPose.value).toBe("sitting");
    expect(controller.catMotion.value).toBe("curious");
    expect(controller.catReaction.value?.text).toBe("喵～");
    harness.runDelay(CAT_CURIOUS_DURATION);
    expect(controller.catPose.value).toBe("idle");
    expect(controller.catMotion.value).toBe("idle");
    controller.dispose();
  });

  it("rejects direct single-fish feeding without changing canonical state", () => {
    const controller = createAmbientController({
      random: createSeededRandom(101),
      storage: null,
    });
    const before = controller.game.value;

    controller.rejectDirectFeed();

    expect(controller.game.value).toBe(before);
    expect(controller.fishFedCount.value).toBe(0);
    expect(controller.status.value).toContain("三条同种小鱼");
    controller.dispose();
  });

  it("persists bond progress across a fresh play session without offline advance", () => {
    const storage = memoryStorage();
    const snapshot = createFreshSnapshot(createSeededRandom(111), 1_000);
    expect(saveAmbientSnapshot(storage, {
      ...snapshot,
      game: { ...snapshot.game, clearCount: 18 },
      pet: { guardedPieceId: null, fishFedCount: 9 },
    })).toBe(true);

    const controller = createAmbientController({
      random: createSeededRandom(112),
      storage,
      now: () => 999_999,
    });

    expect(controller.game.value.level).toBe(1);
    expect(controller.game.value.clearCount).toBe(18);
    expect(controller.fishFedCount.value).toBe(9);
    expect(controller.bondStage.value).toBe("bonded");
    controller.dispose();
  });

  it("opens a harder level only after its final three fish combine", () => {
    const harness = controlledTimers();
    const controller = createAmbientController({
      random: createSeededRandom(121),
      storage: null,
      timers: harness.timers,
    });
    const source = controller.game.value.pieces.slice(0, 3);
    const finalPieces = source.map((piece, index) => ({
      ...piece,
      id: `final-${index}`,
      kind: "whale" as const,
    }));
    controller.game.value = {
      ...controller.game.value,
      pieces: finalPieces,
      tray: [],
      levelProgress: 2,
    };

    for (const piece of finalPieces) controller.activate(piece.id);

    expect(controller.feedback.value).toBe("select");
    expect(controller.game.value.level).toBe(2);
    expect(controller.game.value.clearCount).toBe(1);
    expect(controller.fishFedCount.value).toBe(1);
    expect(controller.completedFish.value?.kind).toBe("whale");
    expect(controller.completedFish.value?.phase).toBe("catching");
    expect(controller.fieldPreview.value).toEqual([]);
    harness.runDelay(FISH_CATCH_FLIGHT_DURATION);
    expect(controller.completedFish.value?.phase).toBe("merging");
    harness.runDelay(FISH_MERGE_CONTACT_DURATION);
    expect(controller.feedback.value).toBe("level");
    expect(controller.completedFish.value?.phase).toBe("feeding");
    expect(controller.fieldPreview.value).toBeNull();
    controller.dispose();
  });

  it("restarts after seven unmatched fish while keeping permanent bond progress", () => {
    const harness = controlledTimers();
    const controller = createAmbientController({
      random: createSeededRandom(131),
      storage: null,
      timers: harness.timers,
    });
    controller.fishFedCount.value = 12;
    const wave = createLevelState(3, 7, 101, createSeededRandom(132), 3);
    const target = {
      ...wave.pieces[0],
      id: "loss-target",
      kind: "pufferfish" as const,
    };
    controller.game.value = {
      ...wave,
      pieces: [target],
      tray: [
        "whale",
        "whale",
        "koi",
        "koi",
        "sardine",
        "sardine",
      ].map((kind, index) => ({
        id: `tray-${index}`,
        kind: kind as "whale" | "koi" | "sardine",
      })),
    };

    controller.activate(target.id);

    expect(controller.feedback.value).toBe("select");
    expect(controller.game.value.level).toBe(3);
    expect(controller.game.value.levelProgress).toBe(3);
    expect(controller.game.value.clearCount).toBe(7);
    expect(controller.game.value.tray).toEqual([]);
    expect(controller.fishFedCount.value).toBe(12);
    expect(controller.canSelect.value).toBe(false);
    expect(controller.catMotion.value).toBe("idle");
    harness.runDelay(FISH_CATCH_FLIGHT_DURATION);
    expect(controller.feedback.value).toBe("loss");
    expect(controller.catMotion.value).toBe("loss");
    harness.runDelay(1_200);
    expect(controller.feedback.value).toBe("idle");
    expect(controller.canSelect.value).toBe(true);
    controller.dispose();
  });
});
