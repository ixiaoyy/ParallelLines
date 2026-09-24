<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";

import {
  getSelectablePieces,
  INITIAL_DISCOVERY_POINT,
  type PilePiece,
  type Point,
} from "../../engine";
import {
  type FocusDirection,
  type GameFeedback,
  type IntroPhase,
} from "../game-ui";
import {
  findNearestMagneticFish,
  findNearestRevealedPiece,
  isPointerTap,
  MAGNETIC_FISH_RADIUS,
  MINIMUM_FISH_TARGET_SIZE,
  moveSpotlight,
  projectFieldPoint,
  unprojectFieldPoint,
  type FieldProjection,
  type FieldSurfaceSize,
  type SpotlightDirection,
  type SpotlightMode,
} from "../spotlight";
import FishPiece from "./FishPiece.vue";

const props = defineProps<{
  pieces: readonly PilePiece[];
  waveSize: number;
  disabled: boolean;
  transitioning: boolean;
  loss: boolean;
  away: boolean;
  projection: FieldProjection;
  surfaceSize: FieldSurfaceSize;
  guidedPieceId: string | null;
  feedback: GameFeedback;
  introPhase: IntroPhase;
  introTargetIds: readonly string[];
}>();

const emit = defineEmits<{
  activate: [pieceId: string];
  searchMiss: [];
  revealedChange: [pieceIds: readonly string[]];
  dragStart: [pieceId: string];
  dragMove: [pieceId: string, clientX: number, clientY: number];
  dragEnd: [pieceId: string, clientX: number, clientY: number];
}>();

const cluster = ref<HTMLElement | null>(null);
const focusedId = ref<string | null>(null);
const activeFocusedId = ref<string | null>(null);
const light = ref<Point | null>(null);
const spotlightMode = ref<SpotlightMode>("inactive");
const draggedPieceId = ref<string | null>(null);
const pointerInside = ref(false);
const focusInside = ref(false);
const magneticPieceId = ref<string | null>(null);
const surfacePressedPieceId = ref<string | null>(null);
const pointerRipple = ref<{
  readonly id: number;
  readonly x: number;
  readonly y: number;
} | null>(null);
let searchPointerId: number | null = null;
let searchPointerStart: Point | null = null;
let searchPointerMoved = false;
let afterglowHandle: ReturnType<typeof setTimeout> | null = null;
let pointerRippleSequence = 0;

const selectable = computed(() => getSelectablePieces(props.pieces));
const guidedPiece = computed(() =>
  props.away || !props.guidedPieceId
    ? null
    : props.pieces.find((piece) => piece.id === props.guidedPieceId) ?? null,
);
const guidedLight = computed(() => guidedPiece.value?.pile ?? null);
const activeSearchLight = computed(() => {
  if (props.away) return null;
  return props.introPhase === "idle" ? light.value : INITIAL_DISCOVERY_POINT;
});
const revealedPieceIds = computed(() => {
  return new Set(props.pieces.map((piece) => piece.id));
});
const projectedLight = computed(() => projectFieldPoint(
  activeSearchLight.value ?? INITIAL_DISCOVERY_POINT,
  props.projection,
));
const guidedSpotlightStyle = computed(() => {
  if (!guidedLight.value) return null;
  const projected = projectFieldPoint(guidedLight.value, props.projection);
  return {
    "--active-light-x": projected.x,
    "--active-light-y": projected.y,
  };
});

watch(
  selectable,
  (pieces) => {
    if (!pieces.some((piece) => piece.id === focusedId.value)) {
      focusedId.value = pieces[0]?.id ?? null;
    }
  },
  { immediate: true },
);

watch(
  revealedPieceIds,
  (ids) => {
    emit("revealedChange", [...ids]);
    if (magneticPieceId.value && !ids.has(magneticPieceId.value)) {
      magneticPieceId.value = null;
    }
  },
  { immediate: true },
);

watch(() => props.away, (away) => {
  if (!away) {
    const activeElement = cluster.value?.ownerDocument.activeElement ?? null;
    const focusedPiece = findPieceElement(activeElement);
    const pieceId = focusedPiece?.dataset.pieceId;
    if (pieceId && cluster.value?.contains(focusedPiece)) {
      revealFocusedPiece(pieceId);
    }
    return;
  }
  clearAfterglow();
  releaseSearchPointerCapture();
  light.value = null;
  spotlightMode.value = "inactive";
  draggedPieceId.value = null;
  activeFocusedId.value = null;
  magneticPieceId.value = null;
  surfacePressedPieceId.value = null;
  pointerInside.value = false;
  focusInside.value = false;
});

function clearAfterglow(): void {
  if (afterglowHandle !== null) {
    globalThis.clearTimeout(afterglowHandle);
    afterglowHandle = null;
  }
}

function onActivate(pieceId: string): void {
  emit("activate", pieceId);
}

function releaseSearchPointerCapture(): void {
  if (
    searchPointerId !== null &&
    cluster.value?.hasPointerCapture(searchPointerId)
  ) {
    cluster.value.releasePointerCapture(searchPointerId);
  }
  searchPointerId = null;
  searchPointerStart = null;
  searchPointerMoved = false;
  surfacePressedPieceId.value = null;
}

function findPieceElement(target: EventTarget | null): HTMLElement | null {
  const candidate = target as HTMLElement | null;
  if (!candidate || typeof candidate.closest !== "function") return null;
  return candidate.closest<HTMLElement>("[data-piece-id]");
}

function startAfterglow(): void {
  clearAfterglow();
  spotlightMode.value = "afterglow";
  afterglowHandle = globalThis.setTimeout(() => {
    afterglowHandle = null;
    if (!draggedPieceId.value) {
      light.value = null;
      spotlightMode.value = "inactive";
    }
  }, 680);
}

function pointFromClient(clientX: number, clientY: number): Point | null {
  const bounds = cluster.value?.getBoundingClientRect();
  if (!bounds || bounds.width === 0 || bounds.height === 0) return null;
  return unprojectFieldPoint({
    x: Math.min(1, Math.max(0, (clientX - bounds.left) / bounds.width)),
    y: Math.min(1, Math.max(0, (clientY - bounds.top) / bounds.height)),
  }, props.projection);
}

function moveLight(clientX: number, clientY: number): void {
  const point = pointFromClient(clientX, clientY);
  if (!point) return;
  clearAfterglow();
  light.value = point;
  if (!draggedPieceId.value) spotlightMode.value = "searching";
}

function focusPiece(pieceId: string): void {
  focusedId.value = pieceId;
  void nextTick(() => {
    cluster.value
      ?.querySelector<HTMLButtonElement>(`[data-piece-id="${pieceId}"]`)
      ?.focus();
  });
}

function revealFocusedPiece(pieceId: string): void {
  if (props.away) return;
  focusedId.value = pieceId;
  activeFocusedId.value = pieceId;
  const piece = props.pieces.find((candidate) => candidate.id === pieceId);
  if (piece) {
    light.value = piece.pile;
    spotlightMode.value = "searching";
  }
}

function navigate(pieceId: string, event: KeyboardEvent): void {
  const directionByKey: Readonly<Record<string, FocusDirection | undefined>> = {
    ArrowUp: "up",
    ArrowRight: "right",
    ArrowDown: "down",
    ArrowLeft: "left",
  };
  const direction = directionByKey[event.key];
  if (!direction) return;
  event.preventDefault();
  const current = selectable.value.find((piece) => piece.id === pieceId);
  if (!current) return;
  const candidates = selectable.value.filter((piece) => piece.id !== pieceId);
  const directional = candidates.filter((piece) => {
    if (direction === "left") return piece.pile.x < current.pile.x;
    if (direction === "right") return piece.pile.x > current.pile.x;
    if (direction === "up") return piece.pile.y < current.pile.y;
    return piece.pile.y > current.pile.y;
  });
  const target = directional.sort((first, second) =>
    Math.hypot(first.pile.x - current.pile.x, first.pile.y - current.pile.y) -
    Math.hypot(second.pile.x - current.pile.x, second.pile.y - current.pile.y)
  )[0];
  if (target) focusPiece(target.id);
}

function onSurfaceKeydown(event: KeyboardEvent): void {
  if (props.away || props.disabled) return;
  if (event.target !== cluster.value) return;
  const directionByKey: Readonly<Record<string, SpotlightDirection | undefined>> = {
    ArrowUp: "up",
    ArrowRight: "right",
    ArrowDown: "down",
    ArrowLeft: "left",
  };
  const direction = directionByKey[event.key];
  if (direction) {
    event.preventDefault();
    light.value = moveSpotlight(light.value, direction, event.shiftKey);
    spotlightMode.value = "searching";
    return;
  }
  if ((event.key === "Enter" || event.key === " ") && light.value) {
    event.preventDefault();
    const target = findNearestRevealedPiece(
      selectable.value,
      revealedPieceIds.value,
      light.value,
    );
    if (target) {
      emit("activate", target.id);
    } else {
      emit("searchMiss");
    }
  }
}

function onPointerDown(event: PointerEvent): void {
  if (props.away || props.disabled) return;
  if (event.button !== 0) return;
  const directPiece = findPieceElement(event.target);
  const magneticTarget = findMagneticPiece(event.clientX, event.clientY);
  if (!directPiece && !magneticTarget) {
    showPointerRipple(event.clientX, event.clientY);
  }
  if (directPiece || event.target !== cluster.value) return;
  searchPointerId = event.pointerId;
  searchPointerStart = { x: event.clientX, y: event.clientY };
  searchPointerMoved = false;
  surfacePressedPieceId.value = magneticTarget;
  cluster.value?.setPointerCapture(event.pointerId);
  moveLight(event.clientX, event.clientY);
}

/**
 * Finds the closest currently revealed fish from rendered target centers.
 * @param clientX Pointer x coordinate in the active document viewport.
 * @param clientY Pointer y coordinate in the active document viewport.
 * @returns The canonical fish ID inside the magnetic radius, or null.
 */
function findMagneticPiece(clientX: number, clientY: number): string | null {
  const bounds = cluster.value?.getBoundingClientRect();
  if (!bounds) return null;
  const selectableIds = new Set(selectable.value.map((piece) => piece.id));
  const elements = cluster.value?.querySelectorAll<HTMLElement>(
    '[data-piece-id][data-revealed="true"]:not(:disabled)',
  ) ?? [];
  const targets = [...elements]
    .filter((element) => {
      const pieceId = element.dataset.pieceId;
      return pieceId ? selectableIds.has(pieceId) : false;
    })
    .flatMap((element) => {
      const pieceId = element.dataset.pieceId;
      if (!pieceId) return [];
      const targetBounds = element.getBoundingClientRect();
      return [{
        id: pieceId,
        center: {
          x: targetBounds.left + targetBounds.width / 2 - bounds.left,
          y: targetBounds.top + targetBounds.height / 2 - bounds.top,
        },
      }];
    });
  return findNearestMagneticFish(targets, {
    x: clientX - bounds.left,
    y: clientY - bounds.top,
  }, MAGNETIC_FISH_RADIUS);
}

/**
 * Restarts the decorative pointer ripple at a surface-local position.
 * @param clientX Pointer x coordinate in the active document viewport.
 * @param clientY Pointer y coordinate in the active document viewport.
 * @returns Nothing; only transient decorative state changes.
 */
function showPointerRipple(
  clientX: number,
  clientY: number,
): void {
  const bounds = cluster.value?.getBoundingClientRect();
  if (!bounds) return;
  pointerRippleSequence += 1;
  pointerRipple.value = {
    id: pointerRippleSequence,
    x: clientX - bounds.left,
    y: clientY - bounds.top,
  };
}

function onPointerMove(event: PointerEvent): void {
  if (props.away || props.disabled) return;
  if (event.pointerType === "mouse" || searchPointerId === event.pointerId) {
    if (
      searchPointerId === event.pointerId &&
      searchPointerStart &&
      !isPointerTap(searchPointerStart, {
        x: event.clientX,
        y: event.clientY,
      })
    ) {
      searchPointerMoved = true;
    }
    pointerInside.value = true;
    moveLight(event.clientX, event.clientY);
    if (event.pointerType === "mouse" && searchPointerId === null) {
      magneticPieceId.value = findMagneticPiece(event.clientX, event.clientY);
    }
  }
}

function onPointerEnd(event: PointerEvent): void {
  if (searchPointerId !== event.pointerId) return;
  const shouldActivate = !searchPointerMoved && light.value !== null;
  const localLight = light.value;
  const capturedPieceId = surfacePressedPieceId.value;
  releaseSearchPointerCapture();
  pointerInside.value = false;
  if (shouldActivate && localLight) {
    if (capturedPieceId) {
      onActivate(capturedPieceId);
      startAfterglow();
      return;
    }
    if (event.pointerType === "mouse") {
      emit("searchMiss");
      startAfterglow();
      return;
    }
    const target = findNearestRevealedPiece(
      selectable.value,
      revealedPieceIds.value,
      localLight,
    );
    if (target) {
      onActivate(target.id);
    } else {
      emit("searchMiss");
    }
  }
  startAfterglow();
}

function onPointerCancel(event: PointerEvent): void {
  if (searchPointerId !== event.pointerId) return;
  releaseSearchPointerCapture();
  pointerInside.value = false;
  startAfterglow();
}

function onPointerLeave(): void {
  pointerInside.value = false;
  if (searchPointerId === null) magneticPieceId.value = null;
  if (!focusInside.value && !draggedPieceId.value) {
    light.value = null;
    spotlightMode.value = "inactive";
  }
}

function onFocusIn(): void {
  focusInside.value = true;
  if (!light.value) {
    light.value = INITIAL_DISCOVERY_POINT;
    spotlightMode.value = "searching";
  }
}

function onFocusOut(event: FocusEvent): void {
  const nextPiece = findPieceElement(event.relatedTarget);
  activeFocusedId.value = nextPiece && cluster.value?.contains(nextPiece)
    ? nextPiece.dataset.pieceId ?? null
    : null;
  if (!cluster.value?.contains(event.relatedTarget as Node | null)) {
    focusInside.value = false;
    if (!pointerInside.value && !draggedPieceId.value) {
      light.value = null;
      spotlightMode.value = "inactive";
    }
  }
}

function onDragStart(pieceId: string): void {
  draggedPieceId.value = pieceId;
  spotlightMode.value = "dragging";
  emit("dragStart", pieceId);
}

function onDragMove(pieceId: string, clientX: number, clientY: number): void {
  moveLight(clientX, clientY);
  spotlightMode.value = "dragging";
  emit("dragMove", pieceId, clientX, clientY);
}

function onDragEnd(pieceId: string, clientX: number, clientY: number): void {
  draggedPieceId.value = null;
  startAfterglow();
  emit("dragEnd", pieceId, clientX, clientY);
}

onBeforeUnmount(() => {
  clearAfterglow();
  releaseSearchPointerCapture();
});
</script>

<template>
  <section
    ref="cluster"
    class="fish-field"
    :data-spotlight="spotlightMode"
    :data-transitioning="transitioning"
    :data-loss="loss"
    :data-feedback="feedback"
    :data-intro="introPhase"
    :data-wave-size="waveSize"
    :style="{
      '--light-x': projectedLight.x,
      '--light-y': projectedLight.y,
      '--fish-target-size': `${MINIMUM_FISH_TARGET_SIZE}px`,
    }"
    tabindex="0"
    aria-label="小鱼搜索桌面。所有小鱼都可选择；用方向键移动焦点，Enter选择小鱼。"
    @pointerdown="onPointerDown"
    @pointermove="onPointerMove"
    @pointerup="onPointerEnd"
    @pointercancel="onPointerCancel"
    @pointerleave="onPointerLeave"
    @focusin="onFocusIn"
    @focusout="onFocusOut"
    @keydown="onSurfaceKeydown"
  >
    <div
      class="fish-field__spotlight fish-field__spotlight--pointer"
      aria-hidden="true"
    >
      <span class="fish-field__spotlight-lens" />
    </div>

    <div
      v-if="guidedSpotlightStyle"
      class="fish-field__spotlight fish-field__spotlight--guided"
      :style="guidedSpotlightStyle"
      aria-hidden="true"
    >
      <span class="fish-field__spotlight-lens" />
    </div>

    <span
      v-if="pointerRipple"
      :key="pointerRipple.id"
      class="fish-field__pointer-ripple"
      :style="{
        '--ripple-x': `${pointerRipple.x}px`,
        '--ripple-y': `${pointerRipple.y}px`,
      }"
      aria-hidden="true"
    />

    <TransitionGroup name="fish-field-piece">
      <FishPiece
        v-for="piece in pieces"
        :key="piece.id"
        :piece="piece"
        :position="projectFieldPoint(piece.pile, projection)"
        :revealed="revealedPieceIds.has(piece.id)"
        :hinted="false"
        :guided="guidedPiece?.id === piece.id"
        :higher-overlap-count="0"
        :disabled="disabled"
        :separation="{ x: 0, y: 0 }"
        :slip-direction="0"
        :intro-target="
          introPhase === 'targets' && introTargetIds.includes(piece.id)
        "
        :arriving="transitioning"
        :magnetic="magneticPieceId === piece.id"
        :surface-pressed="surfacePressedPieceId === piece.id"
        :tab-index="piece.id === focusedId ? 0 : -1"
        @activate="onActivate"
        @focus="revealFocusedPiece"
        @navigate="navigate"
        @drag-start="onDragStart"
        @drag-move="onDragMove"
        @drag-end="onDragEnd"
      />
    </TransitionGroup>
  </section>
</template>

<style scoped lang="scss">
.fish-field {
  --spotlight-radius-x: 12%;
  --spotlight-radius-y: 17%;
  --spotlight-width: 24%;
  --spotlight-height: 34%;
  --fish-visual-size: clamp(72px, min(8.4vw, 13.5vh), 128px);

  position: absolute;
  z-index: 3;
  inset: 0;
  isolation: isolate;
  outline: none;
  touch-action: none;

  &[data-wave-size="11"] {
    --fish-visual-size: clamp(68px, min(7.4vw, 12vh), 112px);
  }

  &[data-wave-size="13"] {
    --fish-visual-size: clamp(64px, min(6.8vw, 11vh), 100px);
  }

  &[data-wave-size="15"] {
    --fish-visual-size: clamp(60px, min(6.2vw, 10vh), 90px);
  }

  &[data-wave-size="17"] {
    --fish-visual-size: clamp(56px, min(5.6vw, 9vh), 82px);
  }

  &:focus-visible {
    outline: none;
  }

  &:focus-visible &__spotlight--pointer &__spotlight-lens {
    border-color: rgb(60 85 126 / 44%);
    box-shadow:
      inset 0 0 38px rgb(255 250 220 / 16%),
      0 0 0 2px rgb(60 85 126 / 10%),
      0 8px 22px rgb(57 70 112 / 10%);
  }

  &[data-loss="true"] {
    animation: fish-field-loss 1.2s var(--ease-out) both;
  }

  &__spotlight {
    --active-light-x: var(--light-x);
    --active-light-y: var(--light-y);

    position: absolute;
    z-index: 1;
    inset: 0;
    overflow: hidden;
    opacity: 0;
    pointer-events: none;
    transition: opacity 180ms ease;

    &::before,
    &::after {
      position: absolute;
      inset: 0;
      content: "";
    }

    &::before {
      display: none;
    }

    &::after {
      background: radial-gradient(
        ellipse var(--spotlight-radius-x) var(--spotlight-radius-y)
          at calc(var(--active-light-x) * 100%) calc(var(--active-light-y) * 100%),
        rgb(255 251 230 / 32%) 0%,
        rgb(244 247 255 / 12%) 58%,
        transparent 100%
      );
    }

    &--guided {
      opacity: 1;

      &::before {
        display: none;
      }

      &::after {
        background: radial-gradient(
          ellipse var(--spotlight-radius-x) var(--spotlight-radius-y)
            at calc(var(--active-light-x) * 100%) calc(var(--active-light-y) * 100%),
          rgb(255 247 194 / 46%) 0%,
          rgb(255 238 170 / 20%) 58%,
          transparent 100%
        );
      }

      .fish-field__spotlight-lens {
        border-color: rgb(255 237 160 / 78%);
        box-shadow:
          inset 0 0 32px rgb(255 245 196 / 32%),
          0 8px 26px rgb(187 139 67 / 24%);
      }
    }
  }

  &__spotlight-lens {
    position: absolute;
    z-index: 1;
    left: calc(var(--active-light-x) * 100%);
    top: calc(var(--active-light-y) * 100%);
    width: var(--spotlight-width);
    height: var(--spotlight-height);
    border: 1px solid rgb(255 252 231 / 34%);
    border-radius: 50%;
    box-shadow:
      inset 0 0 38px rgb(255 250 220 / 14%),
      0 8px 22px rgb(57 70 112 / 9%);
    transform: translate(-50%, -50%);
  }

  &[data-spotlight="searching"] &__spotlight--pointer,
  &[data-spotlight="dragging"] &__spotlight--pointer,
  &[data-spotlight="afterglow"] &__spotlight--pointer {
    opacity: 1;
  }

  &[data-spotlight="searching"] &__spotlight--pointer &__spotlight-lens {
    animation: spotlight-search-breathe 1.35s ease-in-out infinite;
  }

  &[data-intro="scan"] &__spotlight--pointer,
  &[data-intro="targets"] &__spotlight--pointer,
  &[data-intro="tray"] &__spotlight--pointer {
    opacity: 1;
  }

  &[data-intro="scan"] &__spotlight--pointer {
    animation: intro-spotlight-arrive 520ms var(--ease-out) both;
  }

  &[data-spotlight="afterglow"] &__spotlight--pointer {
    opacity: 0.72;
    transition-duration: 420ms;
  }

  &[data-spotlight="dragging"] &__spotlight--pointer &__spotlight-lens {
    border-color: rgb(255 244 197 / 46%);
    box-shadow:
      inset 0 0 28px rgb(255 238 176 / 22%),
      0 0 20px rgb(255 223 148 / 18%);
  }

  &__pointer-ripple {
    position: absolute;
    z-index: 7;
    left: var(--ripple-x);
    top: var(--ripple-y);
    width: 24px;
    height: 14px;
    border: 1.5px solid rgb(109 139 184 / 34%);
    border-radius: 50%;
    box-shadow: 0 4px 10px rgb(70 92 142 / 8%);
    pointer-events: none;
    transform: translate(-50%, -50%);
    animation: fish-pointer-ripple 420ms var(--ease-out) both;
  }
}

.fish-field[data-feedback="clear"] :deep(.fish-field-piece-leave-active),
.fish-field[data-feedback="refresh"] :deep(.fish-field-piece-leave-active),
.fish-field[data-feedback="level"] :deep(.fish-field-piece-leave-active) {
  pointer-events: none;
  animation: fish-origin-tuck 220ms var(--ease-out) both;
}

.fish-field[data-feedback="select"] :deep(.fish-field-piece-leave-active) {
  visibility: hidden;
  pointer-events: none;
  animation: none;
  transition: none;
}

.fish-field :deep(.fish-field-piece-leave-active:focus-visible) {
  outline: none;
}

@media (max-width: 620px) {
  .fish-field {
    --spotlight-radius-x: 18%;
    --spotlight-radius-y: 12.5%;
    --spotlight-width: 36%;
    --spotlight-height: 25%;
  }
}

@media (orientation: portrait) and (min-width: 621px) {
  .fish-field {
    --spotlight-radius-x: 24%;
    --spotlight-radius-y: 11%;
    --spotlight-width: 52%;
    --spotlight-height: 22%;
  }
}

@media (max-height: 620px) and (orientation: landscape) {
  .fish-field {
    --spotlight-radius-y: 12.5%;
    --spotlight-height: 25%;
  }
}

@keyframes intro-spotlight-arrive {
  0% { opacity: 0; transform: translate(-7%, 5%); }
  100% { opacity: 1; transform: none; }
}

@keyframes spotlight-search-breathe {
  0%, 100% { filter: brightness(0.98); }
  50% { filter: brightness(1.08); }
}

@keyframes fish-pointer-ripple {
  0% { opacity: 0; transform: translate(-50%, -50%) scale(0.42); }
  24% { opacity: 0.86; }
  100% { opacity: 0; transform: translate(-50%, -50%) scale(2.25, 1.7); }
}

@keyframes fish-origin-tuck {
  0% {
    opacity: 1;
    transform:
      translate(
        calc(-50% + var(--separation-x)),
        calc(-50% + var(--separation-y) + var(--layer-lift))
      );
  }

  100% {
    opacity: 0;
    transform:
      translate(
        calc(-50% + var(--separation-x)),
        calc(-50% + var(--separation-y) + var(--layer-lift) + 6px)
      );
  }
}

@media (prefers-reduced-motion: reduce) {
  .fish-field[data-loss="true"] {
    animation: none;
  }

  .fish-field[data-loss="true"] {
    filter: brightness(0.88) saturate(0.68);
  }

  .fish-field__spotlight {
    transition: none;
    animation: none !important;
  }

  .fish-field__pointer-ripple {
    animation-duration: 180ms;
  }

  .fish-field :deep(.fish-field-piece-leave-active) {
    animation: none !important;
    opacity: 0;
  }
}

@keyframes fish-field-loss {
  0% { filter: none; }
  24%, 70% { filter: brightness(0.82) saturate(0.62); }
  100% { filter: none; }
}
</style>
