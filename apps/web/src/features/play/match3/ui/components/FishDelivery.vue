<script setup lang="ts">
import { computed } from "vue";

import type { FishKind } from "../../engine";
import { getFishPresentation } from "../game-ui";

const props = defineProps<{
  kind: FishKind;
  startX: number;
  startY: number;
  endX: number;
  endY: number;
}>();

const presentation = computed(() => getFishPresentation(props.kind));
const deliveryStyle = computed(() => ({
  "--delivery-start-x": `${props.startX}px`,
  "--delivery-start-y": `${props.startY}px`,
  "--delivery-dx": `${props.endX - props.startX}px`,
  "--delivery-dy": `${props.endY - props.startY}px`,
}));
</script>

<template>
  <div class="fish-delivery" :style="deliveryStyle" aria-hidden="true">
    <span class="fish-delivery__merge">
      <img
        v-for="index in 3"
        :key="index"
        class="fish-delivery__small"
        :class="`fish-delivery__small--${index}`"
        :src="presentation.assetUrl"
        alt=""
        width="512"
        height="512"
        draggable="false"
      />
      <span class="fish-delivery__glow" />
    </span>
    <img
      class="fish-delivery__large"
      :src="presentation.assetUrl"
      alt=""
      width="512"
      height="512"
      draggable="false"
    />
  </div>
</template>

<style scoped lang="scss">
.fish-delivery {
  position: absolute;
  z-index: 14;
  top: var(--delivery-start-y);
  left: var(--delivery-start-x);
  width: 0;
  height: 0;
  pointer-events: none;

  &__merge,
  &__small,
  &__large,
  &__glow {
    position: absolute;
    display: block;
  }

  &__small {
    top: -25px;
    left: -25px;
    width: 50px;
    height: 50px;
    object-fit: contain;
    filter: drop-shadow(0 6px 6px rgb(57 70 112 / 18%));
    animation: small-fish-merge 300ms var(--ease-out) both;
  }

  &__small--1 {
    --small-x: -42px;
    --small-y: 9px;
  }

  &__small--2 {
    --small-x: 0px;
    --small-y: -18px;
  }

  &__small--3 {
    --small-x: 42px;
    --small-y: 9px;
  }

  &__glow {
    top: -26px;
    left: -26px;
    width: 52px;
    height: 52px;
    border-radius: 50%;
    background: rgb(255 242 190 / 52%);
    filter: blur(7px);
    animation: large-fish-glow 380ms ease-out 180ms both;
  }

  &__large {
    top: -61px;
    left: -61px;
    width: 122px;
    height: 122px;
    object-fit: contain;
    filter:
      drop-shadow(0 10px 10px rgb(57 70 112 / 20%))
      brightness(1.04);
    transform-origin: center;
    animation: large-fish-deliver 700ms var(--ease-out) both;
  }
}

@keyframes small-fish-merge {
  0% {
    opacity: 1;
    transform: translate(var(--small-x), var(--small-y)) scale(0.9);
  }

  72% {
    opacity: 1;
    transform: translate(0, 0) scale(0.72);
  }

  100% {
    opacity: 0;
    transform: translate(0, 0) scale(0.46);
  }
}

@keyframes large-fish-glow {
  0% { opacity: 0; transform: scale(0.45); }
  38% { opacity: 0.9; }
  100% { opacity: 0; transform: scale(1.8); }
}

@keyframes large-fish-deliver {
  0%, 27% {
    opacity: 0;
    transform: scale(0.48);
  }

  38% {
    opacity: 1;
    transform: scale(0.92);
  }

  68% {
    opacity: 1;
    transform:
      translate(
        calc(var(--delivery-dx) * 0.52),
        calc(var(--delivery-dy) * 0.52 - 34px)
      )
      scale(1.04);
  }

  94% {
    opacity: 1;
  }

  100% {
    opacity: 0;
    transform:
      translate(var(--delivery-dx), var(--delivery-dy))
      scale(0.7);
  }
}

@media (max-width: 620px) {
  .fish-delivery__small {
    top: -19px;
    left: -19px;
    width: 38px;
    height: 38px;
  }

  .fish-delivery__large {
    top: -45px;
    left: -45px;
    width: 90px;
    height: 90px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .fish-delivery__small,
  .fish-delivery__glow {
    display: none;
  }

  .fish-delivery__large {
    opacity: 1;
    animation: none;
    filter:
      drop-shadow(0 0 8px rgb(255 235 174 / 52%))
      brightness(1.06);
    transform:
      translate(var(--delivery-dx), var(--delivery-dy))
      scale(0.7);
  }
}
</style>
