<script setup lang="ts">
import { computed, ref } from "vue";

import type { PilePiece, Point } from "../../engine";
import { getFishAccessibleLabel, getFishPresentation } from "../game-ui";
import { isPointerTap } from "../spotlight";

const props = defineProps<{
  piece: PilePiece;
  position: Point;
  revealed: boolean;
  hinted: boolean;
  guided: boolean;
  higherOverlapCount: number;
  tabIndex: number;
  disabled: boolean;
  separation: Point;
  slipDirection: -1 | 0 | 1;
  introTarget: boolean;
  arriving: boolean;
  magnetic: boolean;
  surfacePressed: boolean;
}>();

const emit = defineEmits<{
  activate: [pieceId: string];
  focus: [pieceId: string];
  navigate: [pieceId: string, event: KeyboardEvent];
  dragStart: [pieceId: string];
  dragMove: [pieceId: string, clientX: number, clientY: number];
  dragEnd: [pieceId: string, clientX: number, clientY: number];
}>();

const dragging = ref(false);
const pressed = ref(false);
const dragX = ref(0);
const dragY = ref(0);
let pointerId: number | null = null;
let pointerStart = { x: 0, y: 0 };
let suppressClick = false;

const presentation = computed(() => getFishPresentation(props.piece.kind));
const label = computed(() => getFishAccessibleLabel({
  kind: props.piece.kind,
  layer: props.piece.layer,
  higherOverlapCount: props.higherOverlapCount,
}));

function onPointerDown(event: PointerEvent): void {
  if (event.button !== 0) return;
  pressed.value = true;
  suppressClick = false;
  pointerId = event.pointerId;
  pointerStart = { x: event.clientX, y: event.clientY };
  dragX.value = 0;
  dragY.value = 0;
  (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
}

function onPointerMove(event: PointerEvent): void {
  if (pointerId !== event.pointerId) return;
  const nextX = event.clientX - pointerStart.x;
  const nextY = event.clientY - pointerStart.y;
  if (
    !dragging.value &&
    isPointerTap(pointerStart, { x: event.clientX, y: event.clientY })
  ) return;
  if (!dragging.value) {
    dragging.value = true;
    emit("dragStart", props.piece.id);
  }
  event.preventDefault();
  dragX.value = nextX;
  dragY.value = nextY;
  emit("dragMove", props.piece.id, event.clientX, event.clientY);
}

function finishDrag(event: PointerEvent): void {
  if (pointerId !== event.pointerId) return;
  pressed.value = false;
  const wasDragging = dragging.value;
  if ((event.currentTarget as HTMLElement).hasPointerCapture(event.pointerId)) {
    (event.currentTarget as HTMLElement).releasePointerCapture(event.pointerId);
  }
  pointerId = null;
  dragging.value = false;
  dragX.value = 0;
  dragY.value = 0;
  if (!wasDragging) {
    return;
  }
  suppressClick = true;
  emit("dragEnd", props.piece.id, event.clientX, event.clientY);
}

function cancelDrag(event: PointerEvent): void {
  if (pointerId !== event.pointerId) return;
  pressed.value = false;
  const wasDragging = dragging.value;
  pointerId = null;
  dragging.value = false;
  dragX.value = 0;
  dragY.value = 0;
  if (wasDragging) emit("dragEnd", props.piece.id, Number.NaN, Number.NaN);
}

function onClick(event: MouseEvent): void {
  if (suppressClick && event.detail !== 0) {
    suppressClick = false;
    return;
  }
  suppressClick = false;
  emit("activate", props.piece.id);
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key.toLowerCase() === "f") {
    event.preventDefault();
    emit("activate", props.piece.id);
    return;
  }
  emit("navigate", props.piece.id, event);
}
</script>

<template>
  <button
    class="fish-piece"
    type="button"
    :data-piece-id="piece.id"
    :data-kind="piece.kind"
    :data-revealed="revealed"
    :data-hinted="hinted"
    :data-guided="guided"
    :data-layer="piece.layer"
    :data-dragging="dragging"
    :data-slipping="slipDirection !== 0"
    :data-intro-target="introTarget"
    :data-arriving="arriving"
    :data-magnetic="magnetic"
    :data-pressed="pressed || surfacePressed"
    :disabled="disabled"
    :tabindex="tabIndex"
    :aria-label="label"
    aria-keyshortcuts="F"
    :style="{
      '--pile-x': position.x,
      '--pile-y': position.y,
      '--piece-rotation': `${piece.rotation}deg`,
      '--piece-scale': piece.scale,
      '--piece-scale-tuck': piece.scale * 0.72,
      '--piece-scale-intro': piece.scale * 1.035,
      '--piece-scale-arrive': piece.scale * 0.96,
      '--piece-layer': piece.layer,
      '--layer-lift': `${piece.layer * -3}px`,
      '--layer-shadow-y': `${7 + piece.layer * 3}px`,
      '--layer-shadow-blur': `${7 + piece.layer * 2}px`,
      '--layer-delay': `${Math.round((piece.pile.x + piece.pile.y) * 110)}ms`,
      '--separation-x': `${separation.x}px`,
      '--separation-y': `${separation.y}px`,
      '--drag-x': `${dragX}px`,
      '--drag-y': `${dragY}px`,
      '--slip-x': `${slipDirection * 9}px`,
      '--slip-rotation': `${slipDirection * 3}deg`,
      '--swim-x': `${piece.pile.y < 0.42 ? 4 : -4}px`,
      '--swim-y': `${1.5 + piece.pile.x * 2}px`,
      '--swim-delay': `${-((piece.pile.x * 3.7 + piece.pile.y * 2.9) % 3.8)}s`,
      '--swim-duration': `${4.4 + piece.pile.y * 2}s`,
    }"
    @click="onClick"
    @focus="emit('focus', piece.id)"
    @keydown="onKeydown"
    @pointerdown="onPointerDown"
    @pointermove="onPointerMove"
    @pointerup="finishDrag"
    @pointercancel="cancelDrag"
  >
    <span class="fish-piece__visual" aria-hidden="true">
      <span class="fish-piece__body">
        <img
          :src="presentation.assetUrl"
          alt=""
          width="512"
          height="512"
          draggable="false"
        />
      </span>
    </span>
    <span v-if="guided" class="fish-piece__guide-label" aria-hidden="true">
      这里
    </span>
  </button>
</template>

<style scoped lang="scss">
.fish-piece {
  --active-x: var(--pile-x);
  --active-y: var(--pile-y);
  --piece-visual-size: var(
    --fish-visual-size,
    clamp(72px, min(8.4vw, 13.5vh), 128px)
  );
  position: absolute;
  z-index: calc(2 + var(--piece-layer));
  width: max(
    var(--fish-target-size, 44px),
    calc(var(--piece-visual-size) * 0.86)
  );
  height: max(
    var(--fish-target-size, 44px),
    calc(var(--piece-visual-size) * 0.86)
  );
  padding: 0;
  border: 0;
  border-radius: 44%;
  background: transparent;
  cursor: pointer;
  opacity: 0;
  pointer-events: none;
  touch-action: none;
  left: calc(var(--active-x) * 100%);
  top: calc(var(--active-y) * 100%);
  transform:
    translate(
      calc(-50% + var(--separation-x)),
      calc(-50% + var(--separation-y) + var(--layer-lift))
    );
  transition:
    left 520ms var(--ease-out),
    top 520ms var(--ease-out),
    transform 220ms var(--ease-out),
    opacity 220ms var(--ease-out);

  &[data-revealed="true"],
  &[data-dragging="true"] {
    opacity: 1;
  }

  &[data-hinted="true"]:not([data-revealed="true"]):not([data-dragging="true"]) {
    opacity: 0.16;
  }

  &[data-revealed="true"]:not(:disabled),
  &[data-dragging="true"]:not(:disabled) {
    pointer-events: auto;
  }

  &__visual {
    position: absolute;
    top: 50%;
    left: 50%;
    display: block;
    width: var(--piece-visual-size);
    height: var(--piece-visual-size);
    pointer-events: none;
    transform:
      translate(-50%, -50%)
      rotate(var(--piece-rotation))
      scale(var(--piece-scale));
    transform-origin: 50% 72%;
    transition:
      transform 220ms var(--ease-out),
      filter 220ms var(--ease-out);
  }

  &__visual img {
    width: 100%;
    height: 100%;
    object-fit: contain;
    pointer-events: none;
    user-select: none;
  }

  &[data-revealed="true"] &__visual,
  &[data-dragging="true"] &__visual {
    filter: drop-shadow(
      0 var(--layer-shadow-y) var(--layer-shadow-blur)
      rgb(57 70 112 / 18%)
    );
  }

  &__body {
    display: block;
    width: 100%;
    height: 100%;
    transform-origin: 50% 70%;
    transition: transform 180ms var(--ease-out);
  }

  &[data-revealed="true"]:not([data-magnetic="true"]):not([data-guided="true"]):not([data-dragging="true"]):not([data-pressed="true"]):not(:focus-visible) &__body {
    animation: fish-living-drift var(--swim-duration) ease-in-out
      var(--swim-delay) infinite;
  }

  &[data-hinted="true"]:not([data-revealed="true"]):not([data-magnetic="true"]) &__body {
    animation: fish-living-drift calc(var(--swim-duration) * 1.35) ease-in-out
      var(--swim-delay) infinite;
  }

  &[data-hinted="true"]:not([data-revealed="true"]) &__visual {
    filter: grayscale(0.3) blur(0.35px)
      drop-shadow(0 5px 8px rgb(57 70 112 / 10%));
    transform:
      translate(-50%, -50%)
      rotate(var(--piece-rotation))
      scale(calc(var(--piece-scale) * 0.96));
  }

  &[data-guided="true"] {
    z-index: 10;
  }

  &[data-magnetic="true"] {
    z-index: 9;
  }

  &[data-magnetic="true"] &__visual {
    transform:
      translate(-50%, -55%)
      rotate(var(--piece-rotation))
      scale(calc(var(--piece-scale) * 1.075));
    filter:
      drop-shadow(0 0 4px rgb(255 248 205 / 76%))
      drop-shadow(0 11px 14px rgb(78 87 126 / 22%));
  }

  &[data-pressed="true"] &__visual {
    transform:
      translate(-50%, -48%)
      rotate(var(--piece-rotation))
      scale(
        calc(var(--piece-scale) * 0.95),
        calc(var(--piece-scale) * 0.9)
      );
    filter:
      brightness(1.09)
      drop-shadow(0 5px 7px rgb(78 87 126 / 20%));
    transition-duration: 100ms;
  }

  &[data-guided="true"] &__visual {
    animation: fish-guided-breathe 1.2s ease-in-out infinite;
    filter:
      drop-shadow(0 0 3px rgb(255 247 198 / 92%))
      drop-shadow(0 8px 13px rgb(187 139 67 / 34%));
  }

  &__guide-label {
    position: absolute;
    z-index: 2;
    top: -30px;
    left: 50%;
    width: max-content;
    padding: 5px 9px;
    border-radius: 999px;
    color: #5f4b2f;
    background: rgb(255 248 218 / 94%);
    box-shadow: 0 7px 18px rgb(95 75 47 / 16%);
    font-size: 12px;
    font-weight: 760;
    line-height: 1;
    pointer-events: none;
    transform: translateX(-50%);
  }

  &:hover:not(:disabled):not([data-dragging="true"]) {
    z-index: 8;
  }

  &:hover:not(:disabled):not([data-dragging="true"]):not([data-pressed="true"]) &__visual {
    transform:
      translate(-50%, -54%)
      rotate(var(--piece-rotation))
      scale(calc(var(--piece-scale) * 1.06));
    filter: drop-shadow(0 10px 12px rgb(78 87 126 / 19%));
  }

  &:focus-visible {
    z-index: 9;
    border-radius: 36%;
    outline: 2px solid rgb(60 85 126 / 56%);
    outline-offset: 3px;
  }

  &[data-slipping="true"]:not([data-dragging="true"]) &__visual {
    animation: fish-nearby-slip 380ms var(--ease-out);
  }

  &[data-intro-target="true"]:not([data-dragging="true"]) &__visual {
    animation: fish-intro-lift 620ms var(--ease-out) both;
    animation-delay: var(--layer-delay);
  }

  &[data-arriving="true"] &__visual {
    animation: fish-layer-arrive 540ms var(--ease-out) both;
    animation-delay: var(--layer-delay);
  }

  &[data-dragging="true"] {
    z-index: 20;
    cursor: grabbing;
    transform:
      translate(
        calc(-50% + var(--separation-x) + var(--drag-x)),
        calc(-50% + var(--separation-y) + var(--layer-lift) + var(--drag-y))
      );
    transition: none;
  }

  &[data-dragging="true"] &__visual {
    filter: drop-shadow(0 13px 14px rgb(57 70 112 / 24%));
    transform:
      translate(-50%, -50%)
      rotate(var(--piece-rotation))
      scale(calc(var(--piece-scale) * 1.06));
    transition: none;
  }
}

@keyframes fish-intro-lift {
  0%, 100% {
    transform:
      translate(-50%, -50%)
      rotate(var(--piece-rotation))
      scale(var(--piece-scale));
    filter: drop-shadow(0 var(--layer-shadow-y) 8px rgb(57 70 112 / 18%));
  }

  48% {
    transform:
      translate(-50%, -58%)
      rotate(var(--piece-rotation))
      scale(var(--piece-scale-intro));
    filter: drop-shadow(0 14px 14px rgb(85 84 130 / 28%)) brightness(1.06);
  }
}

@keyframes fish-guided-breathe {
  0%, 100% {
    transform:
      translate(-50%, -50%)
      rotate(var(--piece-rotation))
      scale(var(--piece-scale));
  }

  50% {
    transform:
      translate(-50%, -54%)
      rotate(var(--piece-rotation))
      scale(calc(var(--piece-scale) * 1.045));
  }
}

@keyframes fish-layer-arrive {
  0% {
    transform:
      translate(-50%, calc(-50% - 12px))
      rotate(var(--piece-rotation))
      scale(var(--piece-scale-arrive));
    filter: blur(1.5px);
  }

  100% {
    transform:
      translate(-50%, -50%)
      rotate(var(--piece-rotation))
      scale(var(--piece-scale));
    filter: drop-shadow(0 var(--layer-shadow-y) 8px rgb(57 70 112 / 18%));
  }
}

@keyframes fish-nearby-slip {
  0%,
  100% {
    transform:
      translate(-50%, -50%)
      rotate(var(--piece-rotation))
      scale(var(--piece-scale));
  }

  52% {
    transform:
      translate(
        calc(-50% + var(--slip-x)),
        calc(-50% + 10px)
      )
      rotate(calc(var(--piece-rotation) + var(--slip-rotation)))
      scale(calc(var(--piece-scale) * 0.98));
    filter: drop-shadow(0 6px 7px rgb(57 70 112 / 16%));
  }
}

@keyframes fish-living-drift {
  0%, 100% { transform: translate(0, 0) rotate(-0.7deg); }
  34% {
    transform: translate(var(--swim-x), calc(var(--swim-y) * -1)) rotate(1deg);
  }
  68% {
    transform: translate(calc(var(--swim-x) * -0.55), var(--swim-y)) rotate(-1.15deg);
  }
}

@media (max-width: 620px) {
  .fish-piece {
    --piece-visual-size: clamp(46px, 15vw, 58px);
    width: max(
      var(--fish-target-size, 44px),
      calc(var(--piece-visual-size) * 0.76)
    );
    height: max(
      var(--fish-target-size, 44px),
      calc(var(--piece-visual-size) * 0.76)
    );
  }
}

@media (prefers-reduced-motion: reduce) {
  .fish-piece {
    transition: none;
  }

  .fish-piece__visual {
    transition: none;
    animation: none !important;
  }

  .fish-piece__body {
    animation: none !important;
    transition: none;
  }

  .fish-piece[data-guided="true"] .fish-piece__visual {
    filter:
      drop-shadow(0 0 3px rgb(255 247 198 / 92%))
      drop-shadow(0 8px 13px rgb(187 139 67 / 34%));
  }

  .fish-piece[data-intro-target="true"] .fish-piece__visual {
    filter: drop-shadow(0 var(--layer-shadow-y) 10px rgb(85 84 130 / 26%))
      brightness(1.04);
  }
}
</style>
