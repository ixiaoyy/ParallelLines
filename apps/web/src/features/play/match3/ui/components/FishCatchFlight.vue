<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted } from "vue";

import type { FishKind } from "../../engine";
import {
  FISH_CATCH_FLIGHT_DURATION,
  getFishPresentation,
} from "../game-ui";

const REDUCED_CATCH_DURATION = 240;

const props = defineProps<{
  kind: FishKind;
  startX: number;
  startY: number;
  endX: number;
  endY: number;
  startSize: number;
  endSize: number;
  startRotation: number;
}>();

const emit = defineEmits<{ complete: [] }>();
const presentation = computed(() => getFishPresentation(props.kind));
const reducedMotion = typeof window !== "undefined" && window.matchMedia(
  "(prefers-reduced-motion: reduce)",
).matches;
const duration = reducedMotion
  ? REDUCED_CATCH_DURATION
  : FISH_CATCH_FLIGHT_DURATION;
const flightStyle = computed(() => ({
  "--catch-start-x": `${props.startX}px`,
  "--catch-start-y": `${props.startY}px`,
  "--catch-dx": `${props.endX - props.startX}px`,
  "--catch-dy": `${props.endY - props.startY}px`,
  "--catch-size": `${props.startSize}px`,
  "--catch-offset": `${props.startSize / -2}px`,
  "--catch-end-scale": `${props.endSize / props.startSize}`,
  "--catch-start-rotation": `${props.startRotation}deg`,
  "--catch-duration": `${duration}ms`,
}));
let completionHandle: ReturnType<typeof setTimeout> | null = null;

onMounted(() => {
  completionHandle = globalThis.setTimeout(() => {
    completionHandle = null;
    emit("complete");
  }, duration);
});

onBeforeUnmount(() => {
  if (completionHandle !== null) globalThis.clearTimeout(completionHandle);
});
</script>

<template>
  <span class="fish-catch-flight" :style="flightStyle" aria-hidden="true">
    <span class="fish-catch-flight__source-ring" />
    <span class="fish-catch-flight__trail fish-catch-flight__trail--one" />
    <span class="fish-catch-flight__trail fish-catch-flight__trail--two" />
    <img
      class="fish-catch-flight__fish"
      :src="presentation.assetUrl"
      alt=""
      width="512"
      height="512"
      draggable="false"
    />
  </span>
</template>

<style scoped lang="scss">
.fish-catch-flight {
  position: absolute;
  z-index: 13;
  top: var(--catch-start-y);
  left: var(--catch-start-x);
  width: 0;
  height: 0;
  pointer-events: none;

  &__fish,
  &__source-ring,
  &__trail {
    position: absolute;
    display: block;
    pointer-events: none;
  }

  &__fish {
    top: var(--catch-offset);
    left: var(--catch-offset);
    width: var(--catch-size);
    height: var(--catch-size);
    object-fit: contain;
    filter:
      drop-shadow(0 9px 10px rgb(57 70 112 / 22%))
      brightness(1.045);
    transform-origin: center;
    animation: fish-catch-flight var(--catch-duration) var(--ease-out) both;
  }

  &__source-ring {
    top: -10px;
    left: -17px;
    width: 34px;
    height: 20px;
    border: 1.5px solid rgb(255 247 207 / 70%);
    border-radius: 50%;
    box-shadow: 0 5px 12px rgb(72 88 132 / 10%);
    animation: fish-catch-source-ring 300ms var(--ease-out) both;
  }

  &__trail {
    top: -4px;
    left: -4px;
    width: 8px;
    height: 8px;
    border: 1px solid rgb(255 255 255 / 78%);
    border-radius: 50%;
    background: rgb(194 218 255 / 16%);
    animation: fish-catch-trail var(--catch-duration) ease-out both;
  }

  &__trail--one {
    --trail-progress: 0.32;
    animation-delay: 55ms;
  }

  &__trail--two {
    --trail-progress: 0.58;
    width: 6px;
    height: 6px;
    animation-delay: 115ms;
  }
}

@keyframes fish-catch-flight {
  0% {
    opacity: 1;
    transform:
      translate(0, 0)
      rotate(var(--catch-start-rotation))
      scale(1);
  }

  18% {
    opacity: 1;
    transform: translate(
      calc(var(--catch-dx) * 0.08),
      calc(var(--catch-dy) * 0.08 - 15px)
    ) rotate(calc(var(--catch-start-rotation) + 3deg)) scale(1.04);
  }

  68% {
    opacity: 1;
    transform: translate(
      calc(var(--catch-dx) * 0.66),
      calc(var(--catch-dy) * 0.66 - 34px)
    ) rotate(calc(var(--catch-start-rotation) - 2deg)) scale(0.88);
  }

  100% {
    opacity: 0.72;
    transform:
      translate(var(--catch-dx), var(--catch-dy))
      rotate(0deg)
      scale(var(--catch-end-scale));
  }
}

@keyframes fish-catch-source-ring {
  0% { opacity: 0; transform: scale(0.4); }
  24% { opacity: 0.84; }
  100% { opacity: 0; transform: scale(2.2, 1.65); }
}

@keyframes fish-catch-trail {
  0%, 18% { opacity: 0; transform: translate(0, 0) scale(0.45); }
  40% { opacity: 0.72; }
  100% {
    opacity: 0;
    transform: translate(
      calc(var(--catch-dx) * var(--trail-progress)),
      calc(var(--catch-dy) * var(--trail-progress) - 18px)
    ) scale(1.35);
  }
}

@media (prefers-reduced-motion: reduce) {
  .fish-catch-flight__source-ring,
  .fish-catch-flight__trail {
    display: none;
  }

  .fish-catch-flight__fish {
    animation-name: fish-catch-reduced;
  }
}

@keyframes fish-catch-reduced {
  0% {
    opacity: 1;
    transform: translate(0, 0) rotate(var(--catch-start-rotation)) scale(1);
  }

  55% { opacity: 0; transform: translate(0, 0) scale(0.94); }

  56%, 100% {
    opacity: 0;
    transform:
      translate(var(--catch-dx), var(--catch-dy))
      scale(var(--catch-end-scale));
  }
}
</style>
