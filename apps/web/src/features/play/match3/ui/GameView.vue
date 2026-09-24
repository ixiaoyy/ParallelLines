<script setup lang="ts">
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from "vue";

import { getLevelConfig, type FishKind } from "../engine";
import { createAmbientController } from "./ambient-controller";
import wallpaperUrl from "./assets/ambient/wallpaper.webp";
import CatCompanion from "./components/CatCompanion.vue";
import FishCatchFlight from "./components/FishCatchFlight.vue";
import FishDelivery from "./components/FishDelivery.vue";
import FishField from "./components/FishField.vue";
import FishTray from "./components/FishTray.vue";
import GrowingPlant from "./components/GrowingPlant.vue";
import QuietControls from "./components/QuietControls.vue";
import { createDocumentPipController } from "./document-pip";
import { createClearSound } from "./sound";
import {
  FULL_FIELD_PROJECTION,
  createFieldProjectionScheduler,
  getFieldProjection,
  type FieldProjectionScheduler,
  type FieldSurfaceSize,
} from "./spotlight";

const surface = ref<HTMLElement | null>(null);
const anchor = ref<HTMLElement | null>(null);
const catDropTarget = ref<HTMLElement | null>(null);
const fishTray = ref<{ $el: HTMLElement } | null>(null);
const draggingPieceId = ref<string | null>(null);
const catchFlights = ref<readonly {
  readonly id: number;
  readonly pieceId: string;
  readonly kind: FishKind;
  readonly startX: number;
  readonly startY: number;
  readonly endX: number;
  readonly endY: number;
  readonly startSize: number;
  readonly endSize: number;
  readonly startRotation: number;
}[]>([]);
const deliveryGeometry = ref<{
  readonly eventId: number;
  readonly startX: number;
  readonly startY: number;
  readonly endX: number;
  readonly endY: number;
} | null>(null);
const playHintDismissed = ref(false);
const pipOpen = ref(false);
const activePipWindow = ref<Window | null>(null);
const fieldProjection = ref(
  typeof window === "undefined"
    ? FULL_FIELD_PROJECTION
    : getFieldProjection(window.innerWidth, window.innerHeight),
);
const surfaceSize = ref<FieldSurfaceSize>(
  typeof window === "undefined"
    ? { width: 1, height: 1 }
    : { width: window.innerWidth, height: window.innerHeight },
);
const clearSound = createClearSound();
let surfaceObserver: ResizeObserver | null = null;
let projectionScheduler: FieldProjectionScheduler | null = null;
let latestSurfaceSize = surfaceSize.value;
let catchFlightSequence = 0;
const game = createAmbientController({
  onClear: () => {
    if (game.soundEnabled.value) clearSound.play();
  },
});
const displayedFieldPieces = computed(() =>
  game.fieldPreview.value ?? game.game.value.pieces
);
const fieldWaveSize = computed(() =>
  getLevelConfig(game.game.value.level).pieceCount
);
const incomingPieceIds = computed(() => new Set(
  catchFlights.value.map((flight) => flight.pieceId),
));
const displayedTrayPieces = computed(() => (
  game.trayPreview.value ?? game.game.value.tray
).filter((piece) => !incomingPieceIds.value.has(piece.id)));
const mergeReady = computed(() => {
  const event = game.completedFish.value;
  if (!event || event.phase === "catching") return false;
  return !event.combined.some((piece) => incomingPieceIds.value.has(piece.id));
});
const showFishDelivery = computed(() => Boolean(
  game.completedFish.value &&
  game.completedFish.value.phase !== "catching" &&
  mergeReady.value &&
  deliveryGeometry.value,
));
const showPlayHint = computed(() =>
  !playHintDismissed.value &&
  game.game.value.level === 1 &&
  game.feedback.value !== "level" &&
  game.feedback.value !== "loss"
);
const levelCue = computed(() => game.game.value.level === 2
  ? "新规则 · 每一波只有一个鱼种有三条"
  : "新一关 · 继续寻找唯一的三条"
);

/**
 * Applies one fish pick and preserves its source-to-tray visual continuity.
 * @param pieceId Canonical fish ID emitted by the revealed field target.
 * @returns Nothing; canonical selection remains owned by the ambient controller.
 */
function activateFish(pieceId: string): void {
  const geometry = measureCatchGeometry(
    pieceId,
    Math.min(6, game.game.value.tray.length),
  );
  const result = game.activate(pieceId);
  if (!result || result.kind === "missing") return;
  playHintDismissed.value = true;
  if (!geometry) return;
  catchFlightSequence += 1;
  catchFlights.value = [...catchFlights.value, {
    id: catchFlightSequence,
    pieceId: result.selected.id,
    kind: result.selected.kind,
    ...geometry,
  }];
}

/**
 * Measures a selected fish center and its pre-selection tray destination.
 * @param pieceId Canonical fish ID whose rendered source is still mounted.
 * @param slotIndex Zero-based tray slot that will receive the selected fish.
 * @returns Surface-local endpoints and rendered handoff metrics, or null when
 * geometry is unavailable.
 */
function measureCatchGeometry(
  pieceId: string,
  slotIndex: number,
): {
  readonly startX: number;
  readonly startY: number;
  readonly endX: number;
  readonly endY: number;
  readonly startSize: number;
  readonly endSize: number;
  readonly startRotation: number;
} | null {
  const surfaceBounds = surface.value?.getBoundingClientRect();
  const source = [...(surface.value?.querySelectorAll<HTMLElement>(
    "[data-piece-id]",
  ) ?? [])].find((element) => element.dataset.pieceId === pieceId);
  const target = fishTray.value?.$el.querySelectorAll<HTMLElement>(
    ".fish-tray__slot",
  )[slotIndex];
  const sourceVisual = source?.querySelector<HTMLElement>(
    ".fish-piece__visual",
  );
  const sourceBounds = sourceVisual?.getBoundingClientRect();
  const targetBounds = target?.getBoundingClientRect();
  if (!surfaceBounds || !sourceVisual || !sourceBounds || !targetBounds) {
    return null;
  }
  const transformValue = getComputedStyle(sourceVisual).transform;
  const transform = transformValue === "none"
    ? new DOMMatrixReadOnly()
    : new DOMMatrixReadOnly(transformValue);
  const renderedScale = Math.hypot(transform.a, transform.b);
  return {
    startX: sourceBounds.left + sourceBounds.width / 2 - surfaceBounds.left,
    startY: sourceBounds.top + sourceBounds.height / 2 - surfaceBounds.top,
    endX: targetBounds.left + targetBounds.width / 2 - surfaceBounds.left,
    endY: targetBounds.top + targetBounds.height / 2 - surfaceBounds.top,
    startSize: sourceVisual.offsetWidth * renderedScale,
    endSize: Math.min(targetBounds.width, targetBounds.height) * 0.82,
    startRotation: Math.atan2(transform.b, transform.a) * (180 / Math.PI),
  };
}

/**
 * Replaces a completed catch ghost with its canonical tray fish.
 * @param flightId UI-only catch flight identifier emitted by its overlay.
 * @returns Nothing; canonical game state is already committed.
 */
function completeCatchFlight(flightId: number): void {
  catchFlights.value = catchFlights.value.filter((flight) =>
    flight.id !== flightId
  );
}

function isInsideCat(clientX: number, clientY: number): boolean {
  const bounds = catDropTarget.value?.getBoundingClientRect();
  return Boolean(
    bounds &&
    clientX >= bounds.left &&
    clientX <= bounds.right &&
    clientY >= bounds.top &&
    clientY <= bounds.bottom,
  );
}

function onFishDragStart(pieceId: string): void {
  draggingPieceId.value = pieceId;
  game.status.value = "单条小鱼不会直接喂食，要先在托盘凑齐三条同种鱼。";
}

function onFishDragEnd(
  pieceId: string,
  clientX: number,
  clientY: number,
): void {
  const accepted = draggingPieceId.value === pieceId &&
    isInsideCat(clientX, clientY);
  draggingPieceId.value = null;
  if (accepted) {
    game.rejectDirectFeed();
  } else {
    game.status.value = "小鱼回到了原处；轻点它可以放入托盘。";
  }
}

/**
 * Measures the current match-gather slot and cat center in surface coordinates.
 * @param eventId Completed-fish event whose delivery should use the geometry.
 * @returns Nothing; the transient delivery projection is updated in place.
 */
function measureDelivery(eventId: number): void {
  const surfaceBounds = surface.value?.getBoundingClientRect();
  const trayBounds = fishTray.value?.$el.getBoundingClientRect();
  const traySlots = fishTray.value?.$el.querySelectorAll<HTMLElement>(
    ".fish-tray__slot",
  );
  const catBounds = catDropTarget.value?.getBoundingClientRect();
  if (!surfaceBounds || !trayBounds || !catBounds) return;
  const preview = game.trayPreview.value ?? [];
  const clearingIndexes = preview.flatMap((piece, index) =>
    game.clearingPieceIds.value.includes(piece.id) ? [index] : []
  );
  const gatherIndex = clearingIndexes[
    Math.floor(clearingIndexes.length / 2)
  ];
  const gatherBounds = gatherIndex === undefined
    ? null
    : traySlots?.[gatherIndex]?.getBoundingClientRect();
  deliveryGeometry.value = {
    eventId,
    startX: (gatherBounds?.left ?? trayBounds.left) +
      (gatherBounds?.width ?? trayBounds.width) / 2 - surfaceBounds.left,
    startY: (gatherBounds?.top ?? trayBounds.top) +
      (gatherBounds?.height ?? trayBounds.height) / 2 - surfaceBounds.top,
    endX: catBounds.left + catBounds.width * 0.5 - surfaceBounds.left,
    endY: catBounds.top + catBounds.height * 0.52 - surfaceBounds.top,
  };
}

watch(
  () => game.completedFish.value,
  async (event) => {
    if (!event) {
      deliveryGeometry.value = null;
      return;
    }
    await nextTick();
    measureDelivery(event.id);
  },
  { flush: "post" },
);

function onPipFocus(): void {
  game.setAway(false);
}

function onPipBlur(): void {
  game.setAway(true);
  clearSound.stop();
}

const pip = createDocumentPipController((nextWindow) => {
  activePipWindow.value?.removeEventListener("focus", onPipFocus);
  activePipWindow.value?.removeEventListener("blur", onPipBlur);
  activePipWindow.value = nextWindow;
  pipOpen.value = nextWindow !== null;
  if (nextWindow) {
    nextWindow.addEventListener("focus", onPipFocus);
    nextWindow.addEventListener("blur", onPipBlur);
    game.setAway(false);
  } else {
    game.setAway(document.hidden || !document.hasFocus());
  }
});

function updateMainAttention(): void {
  if (pipOpen.value) return;
  const away = document.hidden || !document.hasFocus();
  game.setAway(away);
  if (away) {
    clearSound.stop();
  }
}

function toggleSound(): void {
  const next = !game.soundEnabled.value;
  game.setSoundEnabled(next);
  if (!next) clearSound.stop();
}

async function togglePip(): Promise<void> {
  game.takeOverIntro();
  if (pip.opened) {
    pip.close();
    return;
  }
  if (!surface.value || !anchor.value) return;
  game.status.value = "正在打开小窗。";
  const opened = await pip.open(surface.value, anchor.value);
  if (!opened) game.status.value = "小窗没有打开，小鱼还在这里。";
}

onMounted(() => {
  document.addEventListener("visibilitychange", updateMainAttention);
  window.addEventListener("focus", updateMainAttention);
  window.addEventListener("blur", updateMainAttention);
  updateMainAttention();
  game.startReactions();
  projectionScheduler = createFieldProjectionScheduler(
    (projection) => {
      fieldProjection.value = projection;
      surfaceSize.value = latestSurfaceSize;
    },
    (callback) => {
      const frameWindow = surface.value?.ownerDocument.defaultView ?? window;
      const frameId = frameWindow.requestAnimationFrame(() => callback());
      return () => frameWindow.cancelAnimationFrame(frameId);
    },
  );
  if (surface.value && typeof ResizeObserver !== "undefined") {
    surfaceObserver = new ResizeObserver(([entry]) => {
      if (!entry) return;
      latestSurfaceSize = {
        width: entry.contentRect.width,
        height: entry.contentRect.height,
      };
      projectionScheduler?.schedule(
        entry.contentRect.width,
        entry.contentRect.height,
      );
    });
    surfaceObserver.observe(surface.value);
    const bounds = surface.value.getBoundingClientRect();
    latestSurfaceSize = { width: bounds.width, height: bounds.height };
    surfaceSize.value = latestSurfaceSize;
    fieldProjection.value = getFieldProjection(bounds.width, bounds.height);
  }
});

onBeforeUnmount(() => {
  document.removeEventListener("visibilitychange", updateMainAttention);
  window.removeEventListener("focus", updateMainAttention);
  window.removeEventListener("blur", updateMainAttention);
  activePipWindow.value?.removeEventListener("focus", onPipFocus);
  activePipWindow.value?.removeEventListener("blur", onPipBlur);
  surfaceObserver?.disconnect();
  surfaceObserver = null;
  projectionScheduler?.cancel();
  projectionScheduler = null;
  pip.close();
  clearSound.dispose();
  game.dispose();
});
</script>

<template>
  <div
    class="ambient-page"
    :style="{ '--wallpaper-url': `url(${wallpaperUrl})` }"
    :data-away="game.isAway.value"
  >
    <div ref="anchor" class="ambient-anchor">
      <section
        ref="surface"
        class="ambient-surface"
        :class="{ 'ambient-surface--in-pip': pipOpen }"
        :data-away="game.isAway.value"
        :data-feedback="game.feedback.value"
        :data-intro="game.introPhase.value"
        :style="{ '--wallpaper-url': `url(${wallpaperUrl})` }"
        aria-label="毛毡小鱼桌面"
        @pointerdown.capture="game.takeOverIntro"
        @pointermove.capture="game.takeOverIntro"
        @focusin.capture="game.takeOverIntro"
        @keydown.capture="game.takeOverIntro"
      >
        <QuietControls
          :sound-enabled="game.soundEnabled.value"
          :pip-supported="pip.supported"
          :pip-open="pipOpen"
          @toggle-sound="toggleSound"
          @toggle-pip="togglePip"
        />

        <Transition name="play-hint">
          <p v-if="showPlayHint" class="play-hint" aria-hidden="true">
            把桌上的三组三条鱼全部找完
          </p>
        </Transition>

        <Transition name="level-cue">
          <p
            v-if="game.feedback.value === 'level'"
            class="level-cue"
            aria-hidden="true"
          >
            {{ levelCue }}
          </p>
        </Transition>

        <GrowingPlant
          :clear-count="game.presentedClearCount.value"
          :age-days="game.plantAgeDays.value"
          :celebrating="game.feedbackProjection.value.celebratesPlant"
        />

        <div
          ref="catDropTarget"
          class="cat-companion-slot"
        >
          <CatCompanion
            :pose="game.catPose.value"
            :motion="game.catMotion.value"
            :bond-stage="game.bondStage.value"
            :pet-zone="game.catPetZone.value"
            :play-variant="game.catPlayVariant.value"
            :reaction="game.catReaction.value"
            :loss="game.feedbackProjection.value.loss"
            @pet="game.petCat"
            @play="game.playWithCat"
          />
        </div>

        <FishField
          :key="game.game.value.level"
          :pieces="displayedFieldPieces"
          :wave-size="fieldWaveSize"
          :disabled="!game.canSelect.value"
          :transitioning="game.feedbackProjection.value.levelArriving"
          :loss="game.feedbackProjection.value.loss"
          :away="game.isAway.value"
          :projection="fieldProjection"
          :surface-size="surfaceSize"
          :guided-piece-id="null"
          :feedback="game.feedback.value"
          :intro-phase="game.introPhase.value"
          :intro-target-ids="game.introTargetIds.value"
          @activate="activateFish"
          @search-miss="game.announceSearchMiss"
          @drag-start="onFishDragStart"
          @drag-end="onFishDragEnd"
        />

        <FishTray
          ref="fishTray"
          :pieces="displayedTrayPieces"
          :feedback="game.feedback.value"
          :clearing-piece-ids="game.clearingPieceIds.value"
          :intro-tray="game.introPhase.value === 'tray'"
          :merge-ready="mergeReady"
        />

        <FishCatchFlight
          v-for="flight in catchFlights"
          :key="flight.id"
          :kind="flight.kind"
          :start-x="flight.startX"
          :start-y="flight.startY"
          :end-x="flight.endX"
          :end-y="flight.endY"
          :start-size="flight.startSize"
          :end-size="flight.endSize"
          :start-rotation="flight.startRotation"
          @complete="completeCatchFlight(flight.id)"
        />

        <FishDelivery
          v-if="showFishDelivery && game.completedFish.value && deliveryGeometry"
          :key="deliveryGeometry.eventId"
          :kind="game.completedFish.value.kind"
          :start-x="deliveryGeometry.startX"
          :start-y="deliveryGeometry.startY"
          :end-x="deliveryGeometry.endX"
          :end-y="deliveryGeometry.endY"
        />

        <p class="match3-visually-hidden" aria-live="polite" aria-atomic="true">
          {{ game.status.value }}
        </p>
      </section>
    </div>
  </div>
</template>

<style scoped lang="scss">
.ambient-page,
.ambient-surface {
  --ease-out: cubic-bezier(0.22, 1, 0.36, 1);
  color: #29344d;
  font-family: Inter, "Segoe UI Variable", "SF Pro Text", "Segoe UI", "Microsoft YaHei UI", sans-serif;
  font-synthesis: none;
}

/* 小窗会把游戏表面移出论坛页面，隐藏文字样式须随组件样式一起复制。 */
:global(.match3-visually-hidden) {
  position: absolute !important;
  width: 1px !important;
  height: 1px !important;
  overflow: hidden !important;
  clip: rect(0, 0, 0, 0) !important;
  white-space: nowrap !important;
}

.ambient-page {
  position: relative;
  width: 100%;
  min-height: 100vh;
  min-height: 100dvh;
  overflow: hidden;
  background:
    linear-gradient(90deg, rgb(210 218 241 / 8%), rgb(190 202 238 / 12%)),
    var(--wallpaper-url) center / cover no-repeat;
}

.ambient-anchor,
.ambient-surface {
  position: absolute;
  inset: 0;
}

.ambient-surface {
  --scene-tray-bottom: clamp(32px, 3.2vh, 50px);
  --scene-tray-height: clamp(76px, 7vw, 100px);
  --scene-vignette-gap: clamp(112px, 11vh, 160px);
  --scene-companion-base: calc(
    var(--scene-tray-bottom) + var(--scene-tray-height) +
      var(--scene-vignette-gap)
  );
  --scene-plant-base: calc(
    var(--scene-companion-base) + clamp(60px, 6vh, 88px)
  );
  --plant-right: clamp(18px, 2.2vw, 34px);
  --plant-width: clamp(180px, 16vw, 236px);
  --cat-plant-overlap: clamp(18px, 1.8vw, 26px);

  overflow: hidden;
  transition: filter 240ms ease;

  &--in-pip {
    position: relative;
    width: 100vw;
    height: 100vh;
    min-height: 0;
    background:
      linear-gradient(90deg, rgb(210 218 241 / 8%), rgb(190 202 238 / 12%)),
      var(--wallpaper-url) center / cover no-repeat;
  }
}

.ambient-surface[data-away="true"] {
  filter: saturate(0.82) brightness(0.98);
}

.ambient-surface[data-away="true"] :deep(*) {
  animation-play-state: paused !important;
  transition-duration: 0.01ms !important;
}

.play-hint,
.level-cue {
  position: absolute;
  z-index: 11;
  left: 50%;
  width: max-content;
  max-width: calc(100% - 32px);
  margin: 0;
  pointer-events: none;
  transform: translateX(-50%);
}

.play-hint {
  bottom: calc(
    var(--scene-tray-bottom) + var(--scene-tray-height) +
      clamp(24px, 3.6vh, 48px)
  );
  padding: 9px 14px;
  border-radius: 999px;
  color: #3e4964;
  background: rgb(251 252 255 / 90%);
  box-shadow: 0 9px 24px rgb(57 70 112 / 13%);
  font-size: clamp(13px, 1.2vw, 15px);
  font-weight: 720;
  line-height: 1.2;
  text-align: center;
  backdrop-filter: blur(10px);
}

.level-cue {
  top: clamp(74px, 11vh, 112px);
  padding: 12px 17px;
  border-radius: 15px;
  color: #3f4961;
  background: rgb(255 251 238 / 94%);
  box-shadow: 0 12px 30px rgb(57 70 112 / 15%);
  font-size: clamp(14px, 1.4vw, 17px);
  font-weight: 760;
  letter-spacing: -0.01em;
  line-height: 1.2;
  text-align: center;
}

.play-hint-enter-active,
.play-hint-leave-active,
.level-cue-enter-active,
.level-cue-leave-active {
  transition:
    opacity 180ms ease,
    filter 220ms ease,
    transform 240ms var(--ease-out);
}

.play-hint-enter-from,
.play-hint-leave-to,
.level-cue-enter-from,
.level-cue-leave-to {
  opacity: 0;
  filter: blur(2px);
  transform: translateX(-50%) translateY(6px);
}

.cat-companion-slot {
  --cat-companion-width: clamp(300px, 27vw, 380px);

  position: absolute;
  z-index: 7;
  left: calc(
    100% - var(--plant-right) - var(--plant-width) -
      var(--cat-companion-width) + var(--cat-plant-overlap)
  );
  bottom: var(--scene-companion-base);
  pointer-events: none;
}

@media (max-width: 620px) {
  .ambient-page {
    background-position: 43% center;
  }

  .ambient-surface {
    --scene-tray-bottom: 12px;
    --scene-tray-height: 52px;
    --scene-vignette-gap: 12px;
    --scene-plant-base: calc(var(--scene-companion-base) + 34px);
    --plant-right: 4px;
    --plant-width: 108px;
    --cat-plant-overlap: 8px;
  }

  .cat-companion-slot {
    --cat-companion-width: 118px;

    left: calc(
      100% - var(--plant-right) - var(--plant-width) -
        var(--cat-companion-width) + var(--cat-plant-overlap)
    );
    bottom: calc(var(--scene-companion-base) + 28px);
  }

  .play-hint {
    bottom: calc(
      var(--scene-tray-bottom) + var(--scene-tray-height) + 16px
    );
    padding: 8px 12px;
  }

  .level-cue {
    top: 68px;
  }

}

@media (min-width: 621px) and (max-height: 620px) and (orientation: landscape) {
  .ambient-surface:not(.ambient-surface--in-pip) {
    min-height: 620px;
  }
}

@media (max-width: 620px) and (max-height: 430px) {
  .ambient-surface {
    --scene-tray-bottom: 6px;
    --scene-tray-height: 48px;
    --scene-vignette-gap: 2px;
    --scene-plant-base: var(--scene-companion-base);
    --cat-companion-height: 88px;
    --plant-right: 84px;
    --plant-width: 56px;
    --plant-height: 86px;
    --cat-plant-overlap: 4px;
    --fish-tray-side-inset: 16px;
    --fish-tray-padding: 6px 4px;
    --quiet-controls-top: 8px;
    --quiet-controls-right: 8px;
    --quiet-controls-gap: 6px;
    --quiet-control-min-width: 64px;
    --quiet-control-min-height: 44px;
    --quiet-control-padding: 7px 10px;
    --quiet-control-font-size: 14px;

    min-height: 0;
  }

  .ambient-surface .cat-companion-slot {
    --cat-companion-width: 76px;

    bottom: var(--scene-companion-base);
    left: calc(
      100% - var(--plant-right) - var(--plant-width) -
        var(--cat-companion-width) + var(--cat-plant-overlap)
    );
  }
}

@media (prefers-reduced-motion: reduce) {
  .play-hint-enter-active,
  .play-hint-leave-active,
  .level-cue-enter-active,
  .level-cue-leave-active {
    transition: none;
  }
}
</style>
