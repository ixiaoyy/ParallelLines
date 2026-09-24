import { computed, ref, shallowRef } from "vue";

import {
  createLevelState,
  getLevelGoal,
  selectPiece,
  type AmbientGameState,
  type FishKind,
  type PilePiece,
  type RandomSource,
  type SelectionResult,
  type TrayPiece,
} from "../engine";
import {
  AMBIENT_SNAPSHOT_VERSION,
  loadAmbientSnapshotResult,
  resolveBrowserStorage,
  saveAmbientSnapshot,
  type AmbientSnapshotV4,
  type StorageLike,
} from "../session/ambient-storage";
import {
  CAT_CURIOUS_DURATION,
  CAT_PET_DURATION,
  CAT_PLAY_DURATION,
  getFishPresentation,
  getIntroTargetIds,
  FISH_CATCH_FLIGHT_DURATION,
  FISH_FEED_SETTLE_DURATION,
  FISH_MERGE_CONTACT_DURATION,
  projectGameFeedback,
  shouldStartIntro,
  type CatPose,
  type GameFeedback,
  type IntroPhase,
} from "./game-ui";
import {
  chooseCatReaction,
  type CatBondStage,
  type CatMotion,
  type CatPetZone,
  type CatPlayVariant,
  type CatReaction,
  type CatReactionContext,
} from "./cat-reactions";

export interface TimerApi {
  schedule(callback: () => void, delay: number): unknown;
  cancel(handle: unknown): void;
}

export interface AmbientControllerOptions {
  readonly random?: RandomSource;
  readonly reactionRandom?: RandomSource;
  readonly storage?: StorageLike | null;
  readonly timers?: TimerApi;
  readonly onClear?: () => void;
  readonly now?: () => number;
}

export interface CompletedFishEvent {
  readonly id: number;
  readonly kind: FishKind;
  readonly combined: readonly [TrayPiece, TrayPiece, TrayPiece];
  readonly feedCount: number;
  readonly phase: "catching" | "merging" | "feeding";
}

const CAT_BUBBLE_DURATION = 2_400;
const CAT_AUTO_REACTION_MIN_DELAY = 45_000;
const CAT_AUTO_REACTION_JITTER = 30_000;
const DIRECT_FEEDBACK_DURATION = 220;
const INTRO_SCAN_DURATION = 520;
const INTRO_TARGET_DURATION = 620;
const INTRO_TRAY_DURATION = 620;
const LEVEL_FEEDBACK_DURATION = 960;
const LOSS_FEEDBACK_DURATION = 1_200;

const browserTimers: TimerApi = {
  schedule: (callback, delay) => globalThis.setTimeout(callback, delay),
  cancel: (handle) => globalThis.clearTimeout(
    handle as ReturnType<typeof setTimeout>,
  ),
};

/**
 * Projects an unlimited completed-fish count into the three visible bond stages.
 * @param fishFedCount Number of complete fish automatically fed to the cat.
 * @returns The stable newcomer, familiar, or bonded stage.
 */
export function getCatBondStage(fishFedCount: number): CatBondStage {
  if (fishFedCount >= 9) return "bonded";
  if (fishFedCount >= 3) return "familiar";
  return "newcomer";
}

export function createAmbientController(
  options: AmbientControllerOptions = {},
) {
  const random = options.random ?? Math.random;
  const reactionRandom = options.reactionRandom ?? Math.random;
  const storage = options.storage === undefined
    ? resolveBrowserStorage()
    : options.storage;
  const timers = options.timers ?? browserTimers;
  const now = options.now ?? Date.now;
  const currentTime = ref(now());
  const loaded = loadAmbientSnapshotResult(storage, random, currentTime.value);
  const stored = loaded.snapshot;
  const introEligible = shouldStartIntro(stored.game, null);
  // A controller owns one active play session. Durable pet, plant, and sound
  // progress survive while the transient board starts clean.
  const initial: AmbientSnapshotV4 = loaded.loadedFromStorage
    ? {
      ...stored,
      game: createLevelState(1, stored.game.clearCount, 1, random),
      pet: { ...stored.pet, guardedPieceId: null },
    }
    : stored;
  const game = shallowRef<AmbientGameState>(initial.game);
  const presentedClearCount = ref(initial.game.clearCount);
  const soundEnabled = ref(initial.preferences.soundEnabled);
  const fishFedCount = ref(initial.pet.fishFedCount);
  const status = ref("鱼群已经展开。找出三条同种小鱼，把本关的鱼全部找完。");
  const feedback = ref<GameFeedback>("idle");
  const introPhase = ref<IntroPhase>("idle");
  const introTargetIds = shallowRef(getIntroTargetIds(initial.game.pieces));
  const catPose = ref<CatPose>("idle");
  const catMotion = ref<CatMotion>("idle");
  const catPetZone = ref<CatPetZone>("head");
  const catPlayVariant = ref<CatPlayVariant>("pounce");
  const trayPreview = shallowRef<readonly TrayPiece[] | null>(null);
  const fieldPreview = shallowRef<readonly PilePiece[] | null>(null);
  const clearingPieceIds = shallowRef<readonly string[]>([]);
  const completedFish = shallowRef<CompletedFishEvent | null>(null);
  const lossPending = ref(false);
  const catReaction = shallowRef<CatReaction | null>(null);
  const isAway = ref(false);
  let feedbackHandle: unknown = null;
  let catPoseHandle: unknown = null;
  let catReactionHandle: unknown = null;
  let catAutoReactionHandle: unknown = null;
  let catReactionRemaining = 0;
  let catReactionStartedAt = 0;
  let lastCatReactionId: string | null = null;
  let playInteractionSequence = 0;
  let reactionsStarted = false;
  let pendingRestAfterFeed = false;
  let completedFishSequence = 0;
  let generation = 0;
  let feedbackSequence = 0;

  const plantAgeDays = computed(() => Math.max(
    0,
    Math.floor((currentTime.value - initial.plant.plantedAt) / 86_400_000),
  ));
  const bondStage = computed(() => getCatBondStage(fishFedCount.value));
  const feedbackProjection = computed(() => projectGameFeedback(feedback.value));
  const canSelect = computed(() =>
    !isAway.value &&
    !lossPending.value &&
    completedFish.value === null &&
    !feedbackProjection.value.locksInput
  );
  const catIsResting = computed(() =>
    catPose.value === "full" ||
    catPose.value === "lying" ||
    catPose.value === "sleeping"
  );

  function snapshot(): AmbientSnapshotV4 {
    return {
      version: AMBIENT_SNAPSHOT_VERSION,
      game: game.value,
      preferences: { soundEnabled: soundEnabled.value },
      plant: initial.plant,
      pet: {
        guardedPieceId: null,
        fishFedCount: fishFedCount.value,
      },
    };
  }

  function persist(): void {
    saveAmbientSnapshot(storage, snapshot());
  }

  function clearFeedbackTimer(): void {
    feedbackSequence += 1;
    if (feedbackHandle !== null) {
      timers.cancel(feedbackHandle);
      feedbackHandle = null;
    }
  }

  /**
   * Schedules one guarded presentation step on the current feedback sequence.
   * @param delay Milliseconds to wait before advancing the presentation.
   * @param next Callback that owns the next phase or final cleanup.
   * @returns Nothing; stale, away, or disposed controller callbacks are ignored.
   */
  function scheduleFeedbackStep(delay: number, next: () => void): void {
    const token = generation;
    const sequence = feedbackSequence;
    feedbackHandle = timers.schedule(() => {
      if (sequence !== feedbackSequence) return;
      feedbackHandle = null;
      if (token !== generation || isAway.value) return;
      next();
    }, delay);
  }

  function takeOverIntro(): void {
    if (feedback.value !== "intro") return;
    clearFeedbackTimer();
    introPhase.value = "idle";
    feedback.value = "idle";
    status.value = "鱼群还在原处，继续寻找三条同种小鱼。";
  }

  function scheduleIntroStep(delay: number, next: () => void): void {
    const token = generation;
    const sequence = feedbackSequence;
    feedbackHandle = timers.schedule(() => {
      if (sequence !== feedbackSequence) return;
      feedbackHandle = null;
      if (token !== generation || isAway.value || feedback.value !== "intro") {
        return;
      }
      next();
    }, delay);
  }

  function startIntro(): void {
    if (!introEligible) return;
    feedback.value = "intro";
    introPhase.value = "scan";
    status.value = "第一关只有三种小鱼，每一种都有三条。";
    scheduleIntroStep(INTRO_SCAN_DURATION, () => {
      introPhase.value = "targets";
      status.value = "先找到任意一种的三条小鱼。";
      scheduleIntroStep(INTRO_TARGET_DURATION, () => {
        introPhase.value = "tray";
        status.value = "三组都找完，才会进入下一关。";
        scheduleIntroStep(INTRO_TRAY_DURATION, () => {
          introPhase.value = "idle";
          feedback.value = "idle";
          status.value = "鱼群已经展开，把桌上的三组小鱼全部找完。";
        });
      });
    });
  }

  function clearCatPoseTimer(): void {
    if (catPoseHandle !== null) {
      timers.cancel(catPoseHandle);
      catPoseHandle = null;
    }
  }

  function clearCatReactionTimer(): void {
    if (catReactionHandle !== null) {
      timers.cancel(catReactionHandle);
      catReactionHandle = null;
    }
  }

  function clearCatAutoReactionTimer(): void {
    if (catAutoReactionHandle !== null) {
      timers.cancel(catAutoReactionHandle);
      catAutoReactionHandle = null;
    }
  }

  function dismissCatReaction(): void {
    clearCatReactionTimer();
    catReaction.value = null;
    catReactionRemaining = 0;
  }

  function scheduleCatReactionDismiss(delay: number): void {
    clearCatReactionTimer();
    catReactionRemaining = delay;
    catReactionStartedAt = now();
    const token = generation;
    catReactionHandle = timers.schedule(() => {
      catReactionHandle = null;
      if (token !== generation || isAway.value) return;
      catReaction.value = null;
      catReactionRemaining = 0;
    }, delay);
  }

  function showCatReaction(
    context: CatReactionContext,
    duration = CAT_BUBBLE_DURATION,
  ): void {
    const next = chooseCatReaction(context, lastCatReactionId, reactionRandom);
    lastCatReactionId = next.id;
    catReaction.value = next;
    if (!isAway.value) scheduleCatReactionDismiss(duration);
  }

  function scheduleCatAutoReaction(): void {
    clearCatAutoReactionTimer();
    if (!reactionsStarted || isAway.value) return;
    const delay = CAT_AUTO_REACTION_MIN_DELAY +
      Math.floor(reactionRandom() * CAT_AUTO_REACTION_JITTER);
    const token = generation;
    catAutoReactionHandle = timers.schedule(() => {
      catAutoReactionHandle = null;
      if (token !== generation || isAway.value) return;
      if (catMotion.value === "idle") {
        catPose.value = "sitting";
        catMotion.value = "curious";
        showCatReaction(fishFedCount.value > 0 ? "fed" : "idle");
        scheduleCatPose("idle", CAT_CURIOUS_DURATION);
      }
      scheduleCatAutoReaction();
    }, delay);
  }

  function startReactions(): void {
    if (reactionsStarted) return;
    reactionsStarted = true;
    scheduleCatAutoReaction();
  }

  function scheduleCatPose(nextPose: CatPose, delay: number): void {
    clearCatPoseTimer();
    const token = generation;
    catPoseHandle = timers.schedule(() => {
      catPoseHandle = null;
      if (token !== generation || isAway.value) return;
      catPose.value = nextPose;
      if (nextPose === "full") {
        catMotion.value = "resting";
        scheduleCatPose("lying", 520);
      } else if (nextPose === "lying") {
        catMotion.value = "resting";
        scheduleCatPose("sleeping", 520);
      } else if (nextPose === "sleeping") {
        catMotion.value = "sleeping";
        showCatReaction("sleeping");
        scheduleCatPose("idle", 720);
      } else if (nextPose === "idle") {
        pendingRestAfterFeed = false;
        catMotion.value = "idle";
      }
    }, delay);
  }

  function startCatFeedReaction(feedCount: number): void {
    clearCatPoseTimer();
    pendingRestAfterFeed = feedCount % 3 === 0;
    catPose.value = "eating";
    catMotion.value = "feeding";
    scheduleCatPose(pendingRestAfterFeed ? "full" : "idle", 520);
  }

  function resumeCatPoseSequence(): void {
    if (catPose.value === "eating") {
      scheduleCatPose(pendingRestAfterFeed ? "full" : "idle", 520);
    } else if (catPose.value === "full") {
      scheduleCatPose("lying", 520);
    } else if (catPose.value === "lying") {
      scheduleCatPose("sleeping", 520);
    } else if (catPose.value === "sleeping") {
      scheduleCatPose("idle", 720);
    } else {
      catPose.value = "idle";
      catMotion.value = "idle";
    }
  }

  /**
   * Announces that keyboard activation found no fish under the spotlight.
   * @returns Nothing; only transient live-region status is updated.
   */
  function announceSearchMiss(): void {
    takeOverIntro();
    if (isAway.value || !canSelect.value) return;
    status.value = "这里没有小鱼，沿着鱼群的流线继续找。";
  }

  /**
   * Projects a tactile response for the selected part of the cat.
   * @param zone Semantic body zone resolved by the component; keyboard uses head.
   * @returns Nothing; the interaction changes only transient pose and copy.
   */
  function petCat(zone: CatPetZone = "head"): void {
    takeOverIntro();
    if (
      isAway.value ||
      feedback.value === "loss" ||
      catMotion.value === "feeding"
    ) return;
    clearCatPoseTimer();
    pendingRestAfterFeed = false;
    catPetZone.value = zone;
    catMotion.value = "petting";
    if (zone === "head") {
      catPose.value = "idle";
      status.value = bondStage.value === "newcomer"
        ? "小猫试探着把额头靠近你的手。"
        : "小猫眯着眼贴近你的手，轻轻呼噜。";
      showCatReaction("pet-head");
    } else if (zone === "belly") {
      catPose.value = "sitting";
      status.value = "挠到软软的肚子，小猫忍不住晃了起来。";
      showCatReaction("pet-belly");
    } else {
      catPose.value = "excited";
      status.value = "你碰了碰小猫的爪子，它开心地举起双爪回应。";
      showCatReaction("pet-paws");
    }
    scheduleCatPose("idle", CAT_PET_DURATION);
  }

  /**
   * Plays one bounded yarn interaction without changing canonical progress.
   * @returns Nothing; only transient cat motion, reaction, and status are updated.
   */
  function playWithCat(): void {
    takeOverIntro();
    if (
      isAway.value ||
      feedback.value === "loss" ||
      catMotion.value === "feeding"
    ) return;
    clearCatPoseTimer();
    pendingRestAfterFeed = false;
    const variants: readonly CatPlayVariant[] = ["pounce", "bat", "cuddle"];
    const variant = variants[playInteractionSequence % variants.length] ?? "pounce";
    playInteractionSequence += 1;
    catPlayVariant.value = variant;
    catMotion.value = "playing";
    if (variant === "pounce") {
      catPose.value = "idle";
      status.value = "毛线球滚了出去，小猫先蓄力，再轻轻扑了过去。";
      showCatReaction("play-pounce");
    } else if (variant === "bat") {
      catPose.value = "excited";
      status.value = "小猫把毛线球拍到半空，举起双爪等它落下。";
      showCatReaction("play-bat");
    } else {
      catPose.value = "cuddling";
      status.value = "小猫趴了下来，把软软的毛线球抱在爪边。";
      showCatReaction("play-cuddle");
    }
    scheduleCatPose("idle", CAT_PLAY_DURATION);
  }

  function clearTrayFeedback(): void {
    trayPreview.value = null;
    fieldPreview.value = null;
    clearingPieceIds.value = [];
    completedFish.value = null;
    lossPending.value = false;
  }

  function interruptFeedback(): void {
    if (feedback.value !== "idle") {
      clearFeedbackTimer();
      introPhase.value = "idle";
      feedback.value = "idle";
    }
    clearTrayFeedback();
  }

  function settleFeedback(
    kind: Exclude<GameFeedback, "idle">,
    delay: number,
  ): void {
    clearFeedbackTimer();
    introPhase.value = "idle";
    feedback.value = kind;
    scheduleFeedbackStep(delay, () => {
      feedback.value = "idle";
      clearTrayFeedback();
      if (kind === "loss") {
        catPose.value = "idle";
        catMotion.value = "idle";
        status.value = "这一波重新排好了，本关已经找到的组数会保留。";
        scheduleCatAutoReaction();
      }
    });
  }

  /**
   * Runs the ordered catch, merge, and feed phases for one completed fish.
   * @param event Completed-fish payload beginning in the catching phase.
   * @param levelAdvanced Whether feeding should reveal the next fish field.
   * @param fieldRefreshed Whether feeding swaps the outgoing field for a new wave.
   * @param previousStage Bond stage before this completed fish was recorded.
   * @param nextStage Bond stage after this completed fish was recorded.
   * @param fishLabel Human-readable species label used by visible status feedback.
   * @returns Nothing; controller refs advance through timed UI-only phases.
   */
  function startCompletedFishPresentation(
    event: CompletedFishEvent,
    levelAdvanced: boolean,
    fieldRefreshed: boolean,
    previousStage: CatBondStage,
    nextStage: CatBondStage,
    fishLabel: string,
  ): void {
    clearFeedbackTimer();
    introPhase.value = "idle";
    completedFish.value = event;
    feedback.value = "select";
    status.value = `第三条${fishLabel}正在滑进托盘。`;
    scheduleFeedbackStep(FISH_CATCH_FLIGHT_DURATION, () => {
      if (completedFish.value?.id !== event.id) return;
      completedFish.value = { ...event, phase: "merging" };
      status.value = `三条${fishLabel}正在聚拢成一条大鱼。`;
      scheduleFeedbackStep(FISH_MERGE_CONTACT_DURATION, () => {
        if (completedFish.value?.id !== event.id) return;
        completedFish.value = { ...event, phase: "feeding" };
        fieldPreview.value = null;
        presentedClearCount.value = game.value.clearCount;
        feedback.value = levelAdvanced
          ? "level"
          : fieldRefreshed
          ? "refresh"
          : "clear";
        const feedStatus = previousStage !== nextStage
          ? `大${fishLabel}被小猫接住了，你们变得更亲近了。`
          : `大${fishLabel}被小猫接住了。`;
        status.value = levelAdvanced
          ? `${feedStatus} 本关的鱼已经全部找完。`
          : fieldRefreshed
          ? `${feedStatus} 下一波鱼群正在展开。`
          : `${feedStatus} 继续找完桌上的其余小鱼。`;
        startCatFeedReaction(event.feedCount);
        showCatReaction(event.feedCount % 3 === 0 ? "full" : "fed");
        options.onClear?.();
        const settleDuration = levelAdvanced
          ? LEVEL_FEEDBACK_DURATION
          : FISH_FEED_SETTLE_DURATION;
        scheduleFeedbackStep(settleDuration, () => {
          feedback.value = "idle";
          clearTrayFeedback();
          if (levelAdvanced) {
            status.value = "新一关已经开始；这一波只有一个鱼种有三条。";
          } else if (fieldRefreshed) {
            const remaining = getLevelGoal(game.value.level) -
              game.value.levelProgress;
            status.value = `鱼群换好了，找出唯一的三条同种鱼；本关还剩${remaining}组。`;
          } else {
            const remaining = getLevelGoal(game.value.level) -
              game.value.levelProgress;
            status.value = `这一组找齐了，继续找完桌上的另外${remaining}组。`;
          }
        });
      });
    });
  }

  /**
   * Lets the seventh incoming fish land before the tray loss response begins.
   * @returns Nothing; the restarted canonical field remains locked until cleanup.
   */
  function startLossPresentation(): void {
    clearFeedbackTimer();
    introPhase.value = "idle";
    lossPending.value = true;
    feedback.value = "select";
    status.value = "最后一条小鱼正在落入托盘。";
    scheduleFeedbackStep(FISH_CATCH_FLIGHT_DURATION, () => {
      lossPending.value = false;
      catPose.value = "lying";
      catMotion.value = "loss";
      feedback.value = "loss";
      status.value = "托盘装满了，这一波小鱼安静地重新排好。";
      scheduleFeedbackStep(LOSS_FEEDBACK_DURATION, () => {
        feedback.value = "idle";
        clearTrayFeedback();
        catPose.value = "idle";
        catMotion.value = "idle";
        status.value = "这一波重新排好了，本关已经找到的组数会保留。";
        scheduleCatAutoReaction();
      });
    });
  }

  /**
   * Applies one legal fish selection and returns its pure engine outcome.
   * @param pieceId Canonical fish ID chosen by pointer, touch, or keyboard input.
   * @returns The applied engine result, or null while transient input is locked.
   */
  function activate(pieceId: string): SelectionResult | null {
    takeOverIntro();
    if (!canSelect.value) return null;
    currentTime.value = now();
    interruptFeedback();
    const result = selectPiece(game.value, pieceId, random);
    if (result.kind === "missing") return result;

    if (result.kind === "combined") {
      const previousStage = bondStage.value;
      if (result.fieldRefreshed) {
        fieldPreview.value = game.value.pieces.filter((piece) =>
          piece.id !== pieceId
        );
      }
      trayPreview.value = [...game.value.tray, result.selected];
      clearingPieceIds.value = result.combined.map((piece) => piece.id);
      game.value = result.state;
      fishFedCount.value = Math.min(
        Number.MAX_SAFE_INTEGER,
        fishFedCount.value + 1,
      );
      completedFishSequence += 1;
      const completedEvent: CompletedFishEvent = {
        id: completedFishSequence,
        kind: result.fishKind,
        combined: result.combined,
        feedCount: fishFedCount.value,
        phase: "catching",
      };
      const nextStage = bondStage.value;
      const fishLabel = getFishPresentation(result.fishKind).label;
      persist();
      startCompletedFishPresentation(
        completedEvent,
        result.levelAdvanced,
        result.fieldRefreshed,
        previousStage,
        nextStage,
        fishLabel,
      );
      return result;
    }

    game.value = result.state;
    if (result.kind === "lost") {
      trayPreview.value = result.tray;
      clearingPieceIds.value = [];
      completedFish.value = null;
      clearCatPoseTimer();
      clearCatAutoReactionTimer();
      dismissCatReaction();
      pendingRestAfterFeed = false;
      persist();
      startLossPresentation();
      return result;
    }

    status.value = `一条${
      getFishPresentation(result.selected.kind).label
    }滑进了托盘。`;
    persist();
    settleFeedback("select", DIRECT_FEEDBACK_DURATION);
    return result;
  }

  /**
   * Explains why a single small fish cannot be fed directly to the cat.
   * @returns Nothing; canonical game and durable pet progress remain unchanged.
   */
  function rejectDirectFeed(): void {
    takeOverIntro();
    if (!canSelect.value) return;
    interruptFeedback();
    status.value = "先凑齐三条同种小鱼，它们会变成大鱼自动喂给小猫。";
    showCatReaction("unavailable");
    settleFeedback("select", DIRECT_FEEDBACK_DURATION);
  }

  function setSoundEnabled(enabled: boolean): void {
    takeOverIntro();
    soundEnabled.value = enabled;
    status.value = enabled ? "小鱼合成音效已开启。" : "声音已关闭。";
    persist();
  }

  function setAway(away: boolean): void {
    if (away) takeOverIntro();
    if (isAway.value === away) return;
    isAway.value = away;
    currentTime.value = now();
    const lossInterrupted = feedback.value === "loss";
    generation += 1;
    clearFeedbackTimer();
    clearCatPoseTimer();
    clearCatAutoReactionTimer();
    if (away) {
      if (catReaction.value && catReactionHandle !== null) {
        const elapsed = Math.max(0, currentTime.value - catReactionStartedAt);
        catReactionRemaining = Math.max(0, catReactionRemaining - elapsed);
      }
      clearCatReactionTimer();
      feedback.value = "idle";
      clearTrayFeedback();
      presentedClearCount.value = game.value.clearCount;
      if (
        lossInterrupted ||
        catMotion.value === "petting" ||
        catMotion.value === "playing" ||
        catMotion.value === "curious"
      ) {
        catPose.value = "idle";
        catMotion.value = "idle";
      }
      persist();
      return;
    }
    status.value = "还是刚才的样子。";
    if (catReaction.value && catReactionRemaining > 0) {
      scheduleCatReactionDismiss(catReactionRemaining);
    }
    resumeCatPoseSequence();
    scheduleCatAutoReaction();
  }

  function dispose(): void {
    takeOverIntro();
    generation += 1;
    clearFeedbackTimer();
    clearCatPoseTimer();
    clearCatAutoReactionTimer();
    dismissCatReaction();
    clearTrayFeedback();
    persist();
  }

  startIntro();

  return {
    game,
    presentedClearCount,
    soundEnabled,
    fishFedCount,
    bondStage,
    status,
    feedback,
    feedbackProjection,
    introPhase,
    introTargetIds,
    catPose,
    catMotion,
    catPetZone,
    catPlayVariant,
    catReaction,
    catIsResting,
    trayPreview,
    fieldPreview,
    clearingPieceIds,
    completedFish,
    isAway,
    plantAgeDays,
    canSelect,
    activate,
    rejectDirectFeed,
    petCat,
    playWithCat,
    announceSearchMiss,
    takeOverIntro,
    startReactions,
    setSoundEnabled,
    setAway,
    persist,
    dispose,
  };
}
