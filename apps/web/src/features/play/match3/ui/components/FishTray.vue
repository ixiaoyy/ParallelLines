<script setup lang="ts">
import { computed } from "vue";

import type { TrayPiece } from "../../engine";
import {
  getFishPresentation,
  getTrayPressure,
  type GameFeedback,
} from "../game-ui";

const props = defineProps<{
  pieces: readonly TrayPiece[];
  feedback: GameFeedback;
  clearingPieceIds: readonly string[];
  introTray: boolean;
  mergeReady: boolean;
}>();

const pressure = computed(() => getTrayPressure(props.pieces.length));

function isClearing(piece: TrayPiece | undefined): boolean {
  return piece
    ? props.mergeReady && props.clearingPieceIds.includes(piece.id)
    : false;
}

const clearingSlots = computed(() => props.pieces
  .map((piece, index) => props.clearingPieceIds.includes(piece.id) ? index + 1 : -1)
  .filter((index) => index > 0));
const clearingTargetSlot = computed(() =>
  clearingSlots.value[Math.floor(clearingSlots.value.length / 2)] ?? 1,
);

function clearStyle(index: number): Record<string, string | number> {
  const shift = clearingTargetSlot.value - index;
  return {
    "--clear-shift-percent": `${shift * 89.3}%`,
    "--clear-shift-gap": `${shift * 3}px`,
    "--clear-z": 4 + Math.abs(shift),
  };
}
</script>

<template>
  <ol
    class="fish-tray"
    :data-feedback="feedback"
    :data-pressure="pressure"
    :data-intro-tray="introTray"
    :data-empty="pieces.length === 0"
    :data-merge-ready="mergeReady"
    aria-label="小鱼托盘"
  >
    <li
      v-for="index in 7"
      :key="index"
      class="fish-tray__slot"
      :data-clearing="isClearing(pieces[index - 1])"
      :style="clearStyle(index)"
    >
      <Transition name="tray-piece">
        <img
          v-if="pieces[index - 1]"
          :key="pieces[index - 1].id"
          :src="getFishPresentation(pieces[index - 1].kind).assetUrl"
          :alt="getFishPresentation(pieces[index - 1].kind).label"
          width="512"
          height="512"
        />
      </Transition>
      <span
        v-if="isClearing(pieces[index - 1]) && index === clearingTargetSlot"
        class="fish-tray__bubble fish-tray__bubble--one"
        aria-hidden="true"
      />
      <span
        v-if="isClearing(pieces[index - 1]) && index === clearingTargetSlot"
        class="fish-tray__bubble fish-tray__bubble--two"
        aria-hidden="true"
      />
      <span
        v-if="isClearing(pieces[index - 1]) && index === clearingTargetSlot"
        class="fish-tray__bubble fish-tray__bubble--three"
        aria-hidden="true"
      />
      <span v-if="!pieces[index - 1]" class="match3-visually-hidden">空位</span>
    </li>
  </ol>
</template>

<style scoped lang="scss">
.fish-tray {
  position: absolute;
  z-index: 8;
  right: clamp(84px, 12vw, 176px);
  bottom: var(--scene-tray-bottom, 24px);
  display: grid;
  width: min(560px, calc(100vw - 32px));
  min-height: var(--scene-tray-height, 68px);
  padding: 14px 9px;
  margin: 0;
  grid-template-columns: repeat(7, 1fr);
  gap: 3px;
  border: 2px solid rgb(255 255 255 / 68%);
  border-radius: 999px;
  background: rgb(208 216 241 / 26%);
  box-shadow:
    inset 0 3px 3px rgb(255 255 255 / 76%),
    inset 0 -3px 5px rgb(60 72 114 / 14%),
    0 5px 8px rgb(58 69 105 / 9%);
  list-style: none;
  backdrop-filter: blur(9px);
  transition:
    box-shadow 200ms ease,
    transform 200ms var(--ease-out),
    opacity 180ms ease;

  &[data-empty="true"] {
    opacity: 0.92;
    box-shadow:
      inset 0 3px 3px rgb(255 255 255 / 72%),
      inset 0 -3px 5px rgb(60 72 114 / 13%),
      0 5px 8px rgb(58 69 105 / 8%);
  }

  &[data-feedback="clear"],
  &[data-feedback="level"] {
    box-shadow:
      0 0 0 6px rgb(180 148 241 / 12%),
      0 16px 34px rgb(91 74 141 / 15%);
  }

  &[data-pressure="caution"] {
    border-color: rgb(197 166 139 / 62%);
    box-shadow:
      inset 0 -4px 7px rgb(121 88 76 / 14%),
      0 7px 14px rgb(91 71 75 / 12%);
  }

  &[data-pressure="critical"] {
    border-color: rgb(183 125 128 / 68%);
    box-shadow:
      inset 0 -5px 8px rgb(111 62 72 / 18%),
      0 8px 18px rgb(111 62 72 / 15%);
    animation: tray-critical-pressure 2.4s var(--ease-out) infinite;
  }

  &[data-feedback="loss"] {
    border-color: rgb(173 112 124 / 52%);
    box-shadow:
      inset 0 3px 3px rgb(255 255 255 / 62%),
      inset 0 -5px 8px rgb(91 55 76 / 20%),
      0 8px 20px rgb(91 55 76 / 18%);
    animation: fish-tray-loss 1.2s var(--ease-out) both;
  }

  &__slot {
    position: relative;
    display: grid;
    min-width: 0;
    aspect-ratio: 1;
    place-items: center;
    border: 2px solid rgb(255 255 255 / 56%);
    border-radius: 50%;
    background: rgb(148 163 211 / 21%);
    box-shadow:
      inset 0 3px 6px rgb(56 68 110 / 14%),
      inset 0 -2px 3px rgb(255 255 255 / 52%),
      0 1px 2px rgb(255 255 255 / 28%);

    img {
      position: relative;
      z-index: 1;
      width: 82%;
      height: 82%;
      object-fit: contain;
    }

    &[data-clearing="true"] {
      z-index: var(--clear-z);
      background: rgb(255 255 255 / 44%);

      img {
        animation: fish-tray-gather-and-melt 600ms var(--ease-out) both;
      }
    }
  }

  &__bubble {
    position: absolute;
    z-index: 2;
    width: 12px;
    height: 12px;
    border: 1.5px solid rgb(255 255 255 / 90%);
    border-radius: 50%;
    background: rgb(197 216 255 / 22%);
    box-shadow:
      inset 2px 2px 3px rgb(255 255 255 / 48%),
      0 2px 6px rgb(96 109 158 / 12%);
    pointer-events: none;
    animation: fish-tray-bubble 300ms var(--ease-out) 260ms both;

    &--one {
      left: 16%;
      bottom: 18%;
    }

    &--two {
      right: 13%;
      bottom: 22%;
      width: 9px;
      height: 9px;
      animation-delay: 295ms;
    }

    &--three {
      left: 49%;
      bottom: 6%;
      width: 7px;
      height: 7px;
      animation-delay: 330ms;
    }
  }

  &[data-intro-tray="true"] .fish-tray__slot:first-child {
    border-color: rgb(255 244 199 / 76%);
    background: rgb(255 250 226 / 38%);
    animation: tray-intro-breathe 620ms var(--ease-out) both;
  }
}

@keyframes fish-tray-gather-and-melt {
  0% {
    opacity: 1;
    transform: translateX(0) scale(1);
    filter: brightness(1);
  }

  48% {
    opacity: 1;
    transform:
      translateX(calc(var(--clear-shift-percent) + var(--clear-shift-gap)))
      scale(1.06);
    filter: brightness(1.14) saturate(1.06);
  }

  62% {
    opacity: 1;
    transform:
      translateX(calc(var(--clear-shift-percent) + var(--clear-shift-gap)))
      translateY(-1px)
      scale(0.96);
    filter: brightness(1.18) saturate(0.94);
  }

  100% {
    opacity: 0;
    transform:
      translateX(calc(var(--clear-shift-percent) + var(--clear-shift-gap)))
      translateY(-8px)
      scale(0.68);
    filter: brightness(1.2) saturate(0.78);
  }
}

@keyframes fish-tray-bubble {
  0% {
    opacity: 0;
    transform: translateY(2px) scale(0.45);
  }

  24% {
    opacity: 0.9;
  }

  100% {
    opacity: 0;
    transform: translateY(-24px) scale(1.35);
  }
}

@keyframes fish-tray-loss {
  0%, 100% { transform: translateY(0); }
  18% { transform: translateY(3px) scaleY(0.96); }
  34% { transform: translate(-2px, 2px) scaleY(0.97); }
  48% { transform: translate(2px, 1px) scaleY(0.98); }
}

@media (max-width: 620px) {
  .fish-tray {
    right: 50%;
    bottom: var(--scene-tray-bottom, 12px);
    width: calc(100vw - var(--fish-tray-side-inset, 24px));
    min-height: var(--scene-tray-height, 52px);
    padding: var(--fish-tray-padding, 8px 6px);
    transform: translateX(50%);

    &[data-feedback="loss"] {
      animation-name: fish-tray-loss-mobile;
    }
  }
}

@keyframes fish-tray-loss-mobile {
  0%, 100% { transform: translateX(50%); }
  18% { transform: translateX(50%) translateY(3px) scaleY(0.96); }
  34% { transform: translateX(calc(50% - 2px)) translateY(2px); }
  48% { transform: translateX(calc(50% + 2px)) translateY(1px); }
}

@media (prefers-reduced-motion: reduce) {
  .fish-tray {
    transition: none;
    animation: none !important;

    &[data-feedback="loss"] {
      animation: none;
      filter: saturate(0.7) brightness(0.92);
    }
  }

  .fish-tray__slot[data-clearing="true"] img {
    animation: none !important;
    opacity: 0.58;
    filter: brightness(1.1) saturate(0.82);
  }

  .fish-tray__bubble {
    display: none;
  }

  .fish-tray[data-pressure="critical"] {
    outline: 2px solid rgb(158 104 111 / 24%);
    outline-offset: 2px;
  }

  .fish-tray[data-intro-tray="true"] .fish-tray__slot:first-child,
  .tray-piece-enter-active {
    animation: none;
  }
}

.tray-piece-enter-active {
  animation: tray-piece-land 220ms var(--ease-out) both;
}

@keyframes tray-piece-land {
  0% { opacity: 0; transform: translateY(-7px) scale(0.82); }
  62% { opacity: 1; transform: translateY(2px) scale(1.04, 0.96); }
  100% { transform: none; }
}

@keyframes tray-intro-breathe {
  0%, 100% { transform: scale(1); }
  50% {
    transform: scale(0.95);
    box-shadow: inset 0 0 0 5px rgb(255 242 190 / 18%);
  }
}

@keyframes tray-critical-pressure {
  0%, 78%, 100% { filter: none; }
  88% { filter: brightness(0.96) saturate(1.08); }
}
</style>
