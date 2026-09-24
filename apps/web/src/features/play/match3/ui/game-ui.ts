import {
  getBlockerIds,
  type AmbientGameState,
  type FishKind,
  type PilePiece,
} from "../engine";

import catEatingUrl from "./assets/cat/cat-eating.webp";
import catFullUrl from "./assets/cat/cat-full.webp";
import catIdleUrl from "./assets/cat/cat-idle.webp";
import catLyingUrl from "./assets/cat/cat-lying.webp";
import catSleepingUrl from "./assets/cat/cat-sleeping.webp";
import fishAngelfishUrl from "./assets/fish/fish-angelfish.webp";
import fishBettaUrl from "./assets/fish/fish-betta.webp";
import fishClownfishUrl from "./assets/fish/fish-clownfish.webp";
import fishGoldfishUrl from "./assets/fish/fish-goldfish.webp";
import fishKoiUrl from "./assets/fish/fish-koi.webp";
import fishPufferUrl from "./assets/fish/fish-puffer.webp";
import fishSardineUrl from "./assets/fish/fish-sardine.webp";
import fishWhaleUrl from "./assets/fish/fish-whale.webp";
import plantStageBudUrl from "./assets/ambient/plant-stage-bud.webp";
import plantStageLilyOfTheValleyUrl from "./assets/ambient/plant-stage-lily-of-the-valley.webp";
import plantStagePeonyUrl from "./assets/ambient/plant-stage-peony.webp";
import plantStagePomegranateUrl from "./assets/ambient/plant-stage-pomegranate.webp";

export type FocusDirection = "up" | "right" | "down" | "left";
export type PlantStage = "growing" | "flowering" | "fruiting" | "mature";
export type CatPose =
  | "idle"
  | "eating"
  | "full"
  | "lying"
  | "sleeping"
  | "excited"
  | "sitting"
  | "cuddling";
export type IntroPhase = "idle" | "scan" | "targets" | "tray";
export type TrayPressure = "calm" | "caution" | "critical" | "lost";
export type GameFeedback =
  | "idle"
  | "intro"
  | "select"
  | "clear"
  | "refresh"
  | "loss"
  | "level";

export const FISH_CATCH_FLIGHT_DURATION = 500;
export const FISH_MERGE_CONTACT_DURATION = 620;
export const FISH_FEED_SETTLE_DURATION = 380;
export const CAT_PET_DURATION = 680;
export const CAT_PLAY_DURATION = 1_040;
export const CAT_CURIOUS_DURATION = 820;

export interface GameFeedbackProjection {
  readonly locksInput: boolean;
  readonly celebratesPlant: boolean;
  readonly levelArriving: boolean;
  readonly loss: boolean;
}

export interface FishPresentation {
  readonly label: string;
  readonly assetUrl: string;
}

export interface FishAccessibleLabelOptions {
  readonly kind: FishKind;
  readonly layer: number;
  readonly higherOverlapCount: number;
}

export interface PlantStagePresentation {
  readonly label: string;
  readonly assetUrl: string;
}

export interface CatPresentation {
  readonly label: string;
  readonly assetUrl: string;
}

const PRESENTATIONS: Readonly<Record<FishKind, FishPresentation>> = {
  whale: { label: "蓝色毛毡鲸鱼", assetUrl: fishWhaleUrl },
  koi: { label: "白红毛毡锦鲤", assetUrl: fishKoiUrl },
  sardine: { label: "蓝色斑点毛毡沙丁鱼", assetUrl: fishSardineUrl },
  pufferfish: { label: "赭黄色圆鼓毛毡河豚", assetUrl: fishPufferUrl },
  goldfish: { label: "橙白毛毡金鱼", assetUrl: fishGoldfishUrl },
  clownfish: { label: "橙白条纹毛毡小丑鱼", assetUrl: fishClownfishUrl },
  angelfish: { label: "黄黑长鳍毛毡神仙鱼", assetUrl: fishAngelfishUrl },
  betta: { label: "蓝紫长鳍毛毡斗鱼", assetUrl: fishBettaUrl },
};

const PLANT_STAGE_PRESENTATIONS: Readonly<Record<PlantStage, PlantStagePresentation>> = {
  growing: { label: "Growing plant", assetUrl: plantStageBudUrl },
  flowering: { label: "Flowering plant", assetUrl: plantStageLilyOfTheValleyUrl },
  fruiting: { label: "Fruiting plant", assetUrl: plantStagePomegranateUrl },
  mature: { label: "Mature plant", assetUrl: plantStagePeonyUrl },
};

const CAT_PRESENTATIONS: Readonly<Record<CatPose, CatPresentation>> = {
  idle: { label: "橘色毛毡猫安静地站着", assetUrl: catIdleUrl },
  eating: { label: "橘色毛毡猫开心地吃东西", assetUrl: catEatingUrl },
  full: { label: "橘色毛毡猫吃饱了，双爪捧着肚子", assetUrl: catFullUrl },
  lying: { label: "橘色毛毡猫清醒地趴着休息", assetUrl: catLyingUrl },
  sleeping: { label: "橘色毛毡猫正趴着睡觉", assetUrl: catSleepingUrl },
  excited: { label: "橘色毛毡猫开心地举起双爪", assetUrl: catEatingUrl },
  sitting: { label: "橘色毛毡猫坐着等你互动", assetUrl: catFullUrl },
  cuddling: { label: "橘色毛毡猫趴着抱住毛线球", assetUrl: catLyingUrl },
};

export function getFishPresentation(kind: FishKind): FishPresentation {
  return PRESENTATIONS[kind];
}

export function getFishAccessibleLabel({
  kind,
}: FishAccessibleLabelOptions): string {
  return `${getFishPresentation(kind).label}；Enter、空格或F放入托盘`;
}

export function getHigherOverlapCounts(
  pieces: readonly PilePiece[],
): ReadonlyMap<string, number> {
  return new Map(pieces.map((piece) => [
    piece.id,
    getBlockerIds(pieces, piece.id).length,
  ]));
}

export function getPlantStagePresentation(stage: PlantStage): PlantStagePresentation {
  return PLANT_STAGE_PRESENTATIONS[stage];
}

export function getCatPresentation(pose: CatPose): CatPresentation {
  return CAT_PRESENTATIONS[pose];
}

export function getTrayPressure(pieceCount: number): TrayPressure {
  if (pieceCount >= 7) return "lost";
  if (pieceCount === 6) return "critical";
  if (pieceCount === 5) return "caution";
  return "calm";
}

export function projectGameFeedback(
  feedback: GameFeedback,
): GameFeedbackProjection {
  return {
    locksInput: feedback === "loss" || feedback === "level",
    celebratesPlant:
      feedback === "clear" || feedback === "refresh" || feedback === "level",
    levelArriving: feedback === "refresh" || feedback === "level",
    loss: feedback === "loss",
  };
}

export function getIntroTargetIds(
  pieces: readonly PilePiece[],
): readonly string[] {
  const candidatesByKind = new Map<FishKind, PilePiece[]>();
  for (const piece of pieces) {
    const candidates = candidatesByKind.get(piece.kind) ?? [];
    candidates.push(piece);
    candidatesByKind.set(piece.kind, candidates);
  }
  for (const candidates of candidatesByKind.values()) {
    const [first, second, third] = candidates;
    if (first && second && third) return [first.id, second.id, third.id];
  }
  return [];
}

export function shouldStartIntro(
  game: AmbientGameState,
  guardedPieceId: string | null,
): boolean {
  return game.level === 1 &&
    game.clearCount === 0 &&
    game.levelProgress === 0 &&
    game.tray.length === 0 &&
    guardedPieceId === null &&
    game.nextPieceId === game.pieces.length + 1 &&
    getIntroTargetIds(game.pieces).length === 3;
}

export function getGrowthPercent(clearCount: number): number {
  const milestones = [
    { clears: 0, percent: 0 },
    { clears: 1, percent: 4 },
    { clears: 12, percent: 18 },
    { clears: 100, percent: 30 },
    { clears: 300, percent: 42 },
    { clears: 600, percent: 55 },
    { clears: 1_000, percent: 67 },
    { clears: 1_800, percent: 78 },
    { clears: 3_000, percent: 90 },
    { clears: 5_000, percent: 96 },
    { clears: 8_000, percent: 100 },
  ] as const;
  const normalizedCount = Math.max(0, clearCount);
  for (let index = 1; index < milestones.length; index += 1) {
    const upper = milestones[index];
    if (normalizedCount > upper.clears) continue;
    const lower = milestones[index - 1];
    const progress = (normalizedCount - lower.clears) /
      (upper.clears - lower.clears);
    return lower.percent + (upper.percent - lower.percent) * progress;
  }
  return Math.min(104, 100 + (normalizedCount - 8_000) / 2_000);
}

export function getPlantStage(clearCount: number, ageDays: number): PlantStage {
  if (clearCount >= 8_000 && ageDays >= 30) return "mature";
  if (clearCount >= 3_000 && ageDays >= 10) return "fruiting";
  if (clearCount >= 1_000 && ageDays >= 3) return "flowering";
  return "growing";
}
