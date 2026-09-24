<script setup lang="ts">
import { computed } from "vue";

import catCushionUrl from "../assets/cat/cat-cushion.webp";
import catYarnBallUrl from "../assets/cat/cat-yarn-ball.webp";
import {
  resolveCatPetZone,
  type CatBondStage,
  type CatMotion,
  type CatPetZone,
  type CatPlayVariant,
  type CatReaction,
} from "../cat-reactions";
import {
  CAT_CURIOUS_DURATION,
  CAT_PET_DURATION,
  CAT_PLAY_DURATION,
  getCatPresentation,
  type CatPose,
} from "../game-ui";

const props = defineProps<{
  pose: CatPose;
  motion: CatMotion;
  bondStage: CatBondStage;
  petZone: CatPetZone;
  playVariant: CatPlayVariant;
  reaction: CatReaction | null;
  loss: boolean;
}>();
const emit = defineEmits<{ pet: [zone: CatPetZone]; play: [] }>();

const presentation = computed(() => getCatPresentation(props.pose));
const interactionDisabled = computed(() =>
  props.loss || props.motion === "feeding"
);
const actionLabel = computed(() => {
  if (props.loss) {
    return `${presentation.value.label}，托盘已经装满，小鱼正在重新布置`;
  }
  if (props.motion === "feeding") {
    return `${presentation.value.label}，正在吃三条小鱼合成的大鱼`;
  }
  if (props.motion === "playing") {
    return `${presentation.value.label}，正在和毛线球玩`;
  }
  if (props.motion === "petting") {
    return `${presentation.value.label}，正在回应你的抚摸`;
  }
  if (props.motion === "curious") {
    return `${presentation.value.label}，正好奇地看着你`;
  }
  return `${presentation.value.label}，轻点头、肚子或脚边会有不同回应`;
});
const yarnLabel = computed(() => interactionDisabled.value
  ? "毛线球暂时不能玩"
  : "毛线球，点击陪小猫玩；每次会有不同回应"
);

/**
 * Resolves the clicked body region and requests its tactile cat response.
 * @param event Native button click; keyboard activation defaults to the head.
 * @returns Nothing; the semantic body zone is emitted to the controller.
 */
function choosePet(event: MouseEvent): void {
  if (interactionDisabled.value) return;
  const target = event.currentTarget as HTMLButtonElement | null;
  const bounds = target?.getBoundingClientRect();
  const normalizedY = event.detail === 0 || !bounds || bounds.height === 0
    ? 0.25
    : (event.clientY - bounds.top) / bounds.height;
  emit("pet", resolveCatPetZone(normalizedY));
}

/**
 * Requests the next yarn-play variant from the parent controller.
 * @returns Nothing; the controller owns variant rotation and timing.
 */
function choosePlay(): void {
  if (interactionDisabled.value) return;
  emit("play");
}
</script>

<template>
  <div
    class="cat-companion"
    :data-pose="pose"
    :data-motion="motion"
    :data-pet-zone="petZone"
    :data-play-variant="playVariant"
    :data-bond-stage="bondStage"
    :data-loss="loss"
    :style="{
      '--cat-curious-duration': `${CAT_CURIOUS_DURATION}ms`,
      '--cat-pet-duration': `${CAT_PET_DURATION}ms`,
      '--cat-play-duration': `${CAT_PLAY_DURATION}ms`,
    }"
  >
    <button
      class="cat-companion__trigger"
      type="button"
      :aria-label="actionLabel"
      :disabled="interactionDisabled"
      @click="choosePet"
    />

    <img
      v-if="bondStage === 'bonded'"
      class="cat-companion__keepsake cat-companion__keepsake--cushion"
      :src="catCushionUrl"
      alt=""
      width="1254"
      height="1254"
      draggable="false"
    />

    <button
      class="cat-companion__yarn-trigger"
      type="button"
      :aria-label="yarnLabel"
      :disabled="interactionDisabled"
      @click="choosePlay"
    >
      <img
        class="cat-companion__keepsake cat-companion__keepsake--yarn"
        :src="catYarnBallUrl"
        alt=""
        width="1254"
        height="1254"
        draggable="false"
      />
    </button>

    <span class="cat-companion__ground-shadow" aria-hidden="true" />

    <div class="cat-companion__motion" aria-hidden="true">
      <Transition name="cat-pose">
        <img
          :key="pose"
          class="cat-companion__image"
          :src="presentation.assetUrl"
          alt=""
          width="1402"
          height="1254"
          draggable="false"
        />
      </Transition>
      <span class="cat-companion__purr-ring cat-companion__purr-ring--one" />
      <span class="cat-companion__purr-ring cat-companion__purr-ring--two" />
    </div>

    <Transition name="cat-sleep-mark">
      <span
        v-if="pose === 'sleeping'"
        class="cat-companion__sleep-mark"
        aria-hidden="true"
      >
        ZZZ
      </span>
    </Transition>

    <Transition name="cat-bubble" mode="out-in">
      <span
        v-if="reaction"
        :key="reaction.id"
        class="cat-companion__bubble"
        role="status"
        aria-live="polite"
      >
        {{ reaction.text }}
      </span>
    </Transition>
  </div>
</template>

<style scoped lang="scss">
.cat-companion {
  position: relative;
  width: var(--cat-companion-width, clamp(320px, 35vw, 500px));
  height: var(--cat-companion-height, clamp(370px, 40vw, 560px));
  isolation: isolate;
  pointer-events: none;

  &__trigger {
    position: absolute;
    z-index: 2;
    bottom: 2%;
    left: 61%;
    display: block;
    width: 64%;
    min-width: 44px;
    height: 58%;
    min-height: 44px;
    padding: 0;
    border: 0;
    margin: 0;
    border-radius: 46% 46% 40% 40%;
    background: transparent;
    cursor: pointer;
    pointer-events: auto;
    transform: translateX(-50%);
  }

  &__trigger:focus-visible {
    outline: none;
  }

  &[data-pose="lying"] &__trigger,
  &[data-pose="sleeping"] &__trigger,
  &[data-pose="cuddling"] &__trigger {
    bottom: 8%;
    left: 64%;
    width: 68%;
    height: 62%;
    border-radius: 46% 48% 42% 40%;
  }

  &__trigger:disabled,
  &__yarn-trigger:disabled {
    cursor: default;
  }

  &__yarn-trigger {
    position: absolute;
    z-index: 4;
    bottom: 1%;
    left: -8%;
    display: block;
    width: 28%;
    min-width: 44px;
    aspect-ratio: 1;
    padding: 0;
    border: 0;
    border-radius: 50%;
    background: transparent;
    cursor: pointer;
    opacity: 0.92;
    pointer-events: auto;
    transition:
      opacity 150ms ease,
      transform 180ms var(--ease-out),
      filter 180ms ease;
  }

  &__yarn-trigger:not(:disabled):hover {
    opacity: 1;
    transform: translateY(-2px) scale(1.04);
  }

  &__yarn-trigger:focus-visible {
    outline: 2px solid rgb(248 250 255 / 92%);
    outline-offset: 2px;
    filter: drop-shadow(0 0 5px rgb(72 86 134 / 46%));
  }

  &__keepsake {
    position: absolute;
    z-index: 0;
    display: block;
    object-fit: contain;
    pointer-events: none;
    user-select: none;
  }

  &__keepsake--yarn {
    inset: 0;
    width: 100%;
    height: 100%;
    filter: drop-shadow(0 7px 6px rgb(57 70 112 / 15%));
  }

  &__keepsake--cushion {
    right: -1%;
    bottom: -3%;
    width: 98%;
    height: 35%;
    filter: drop-shadow(0 7px 6px rgb(57 70 112 / 13%));
    transform: scaleX(1.65);
  }

  &__ground-shadow {
    position: absolute;
    z-index: 0;
    right: 14%;
    bottom: 2%;
    width: 66%;
    height: 8%;
    border-radius: 50%;
    background: rgb(63 72 107 / 12%);
    filter: blur(6px);
    pointer-events: none;
    transform-origin: center;
  }

  &__motion {
    position: absolute;
    z-index: 1;
    inset: 0;
    pointer-events: none;
    transform-origin: 50% 92%;
  }

  &[data-motion="idle"] &__motion {
    animation: cat-idle-breathe 3.8s ease-in-out infinite;
  }

  &[data-motion="curious"] &__motion {
    animation: cat-curious var(--cat-curious-duration) var(--ease-out) both;
    will-change: transform, filter;
  }

  &[data-motion="feeding"] &__motion {
    animation: cat-catch-and-chew 520ms var(--ease-out) both;
  }

  &[data-motion="feeding"] &__ground-shadow {
    animation: cat-feed-shadow 520ms var(--ease-out) both;
  }

  &[data-motion="petting"][data-pet-zone="head"] &__motion {
    animation: cat-head-nuzzle var(--cat-pet-duration) var(--ease-out) both;
    will-change: transform;
  }

  &[data-motion="petting"][data-pet-zone="belly"] &__motion {
    animation: cat-belly-giggle var(--cat-pet-duration) var(--ease-out) both;
    will-change: transform;
  }

  &[data-motion="petting"][data-pet-zone="paws"] &__motion {
    animation: cat-paws-boop var(--cat-pet-duration) var(--ease-out) both;
    will-change: transform;
  }

  &[data-motion="playing"][data-play-variant="pounce"] &__motion {
    animation: cat-play-pounce var(--cat-play-duration) var(--ease-out) both;
    will-change: transform;
  }

  &[data-motion="playing"][data-play-variant="bat"] &__motion {
    animation: cat-play-bat var(--cat-play-duration) var(--ease-out) both;
    will-change: transform;
  }

  &[data-motion="playing"][data-play-variant="cuddle"] &__motion {
    animation: cat-play-cuddle var(--cat-play-duration) var(--ease-out) both;
    will-change: transform, filter;
  }

  &[data-motion="playing"] &__ground-shadow {
    animation: cat-play-shadow var(--cat-play-duration) var(--ease-out) both;
  }

  &[data-motion="playing"] &__yarn-trigger {
    z-index: 4;
    will-change: transform, filter;
  }

  &[data-motion="playing"][data-play-variant="pounce"] &__yarn-trigger {
    animation: cat-yarn-pounce var(--cat-play-duration) var(--ease-out) both;
  }

  &[data-motion="playing"][data-play-variant="bat"] &__yarn-trigger {
    animation: cat-yarn-bat var(--cat-play-duration) var(--ease-out) both;
  }

  &[data-motion="playing"][data-play-variant="cuddle"] &__yarn-trigger {
    animation: cat-yarn-cuddle var(--cat-play-duration) var(--ease-out) both;
  }

  &[data-motion="loss"] &__motion {
    animation: cat-loss-reaction 1.2s var(--ease-out) both;
  }

  &__image {
    position: absolute;
    z-index: 1;
    inset: 0;
    display: block;
    width: 100%;
    height: 100%;
    object-fit: contain;
    object-position: 50% 100%;
    filter: drop-shadow(0 9px 8px rgb(57 70 112 / 16%));
    pointer-events: none;
    user-select: none;
  }

  &__trigger:hover ~ &__motion &__image {
    filter:
      drop-shadow(0 10px 10px rgb(57 70 112 / 18%))
      brightness(1.025);
  }

  &__trigger:focus-visible ~ &__motion &__image {
    filter:
      drop-shadow(0 0 2px rgb(60 85 126 / 92%))
      drop-shadow(0 0 6px rgb(247 250 255 / 88%))
      drop-shadow(0 10px 10px rgb(57 70 112 / 18%));
  }

  &__sleep-mark {
    position: absolute;
    z-index: 1;
    top: 12%;
    right: 2%;
    color: rgb(69 79 111 / 76%);
    font-size: clamp(11px, 1vw, 14px);
    font-weight: 760;
    letter-spacing: 0.08em;
    text-shadow: 0 2px 5px rgb(255 255 255 / 54%);
  }

  &__bubble {
    position: absolute;
    z-index: 5;
    top: 26%;
    left: 52%;
    width: max-content;
    max-width: 112px;
    padding: 6px 9px;
    border: 1px solid rgb(255 255 255 / 70%);
    border-radius: 14px 14px 14px 4px;
    color: #4b536d;
    background: rgb(250 248 247 / 88%);
    box-shadow: 0 7px 18px rgb(57 70 112 / 13%);
    font-size: 12px;
    font-weight: 650;
    line-height: 1.25;
    pointer-events: none;
    transform: translateX(-50%);
    backdrop-filter: blur(7px);
  }

  &__purr-ring {
    position: absolute;
    z-index: 2;
    top: 35%;
    right: 19%;
    display: block;
    width: 13%;
    aspect-ratio: 1;
    border: 2px solid rgb(208 173 226 / 62%);
    border-radius: 50%;
    opacity: 0;
    pointer-events: none;
  }

  &[data-motion="petting"] &__purr-ring {
    animation: cat-purr-ring var(--cat-pet-duration) ease-out both;
  }

  &[data-motion="petting"] &__purr-ring--two {
    animation-delay: 90ms;
  }

  &[data-motion="petting"][data-pet-zone="belly"] &__purr-ring {
    top: 48%;
    right: 34%;
  }

  &[data-motion="petting"][data-pet-zone="paws"] &__purr-ring {
    top: 36%;
    right: 31%;
    border-color: rgb(244 183 103 / 70%);
  }

  &[data-motion="feeding"] &__purr-ring {
    top: 32%;
    right: 16%;
    border-color: rgb(244 183 103 / 72%);
    animation: cat-bite-ring 430ms ease-out both;
  }

  &[data-motion="feeding"] &__purr-ring--two {
    animation-delay: 70ms;
  }

}

@keyframes cat-idle-breathe {
  0%, 100% { transform: translateY(0) scaleY(1); }
  50% { transform: translateY(-1px) scaleY(1.012); }
}

@keyframes cat-catch-and-chew {
  0%, 100% { transform: translate(0) scale(1) rotate(0); }
  14% { transform: translate(-2px, 4px) scale(1.035, 0.965) rotate(-0.8deg); }
  29% { transform: translate(-8px, -6px) scale(0.985, 1.045) rotate(-1.4deg); }
  45% { transform: translate(-1px, 1px) scale(1.025, 0.98) rotate(0.5deg); }
  62% { transform: translateY(-3px) scale(0.995, 1.018); }
  76% { transform: translateY(2px) scale(1.014, 0.986); }
  88% { transform: translateY(-1px) scale(0.998, 1.008); }
}

@keyframes cat-feed-shadow {
  0%, 100% { opacity: 1; transform: scaleX(1); }
  16% { opacity: 0.88; transform: scaleX(1.08); }
  31% { opacity: 0.58; transform: translateX(-5px) scaleX(0.82); }
  48% { opacity: 0.92; transform: scaleX(1.05); }
}

@keyframes cat-bite-ring {
  0% { opacity: 0; transform: scale(0.35); }
  28% { opacity: 0; transform: scale(0.35); }
  44% { opacity: 0.86; }
  100% { opacity: 0; transform: scale(1.28); }
}

@keyframes cat-curious {
  0%, 100% { transform: translate(0) rotate(0); filter: brightness(1); }
  24% { transform: translateY(1%) rotate(-1deg); }
  52% { transform: translateY(-2%) rotate(2deg); filter: brightness(1.035); }
  78% { transform: translateY(-1%) rotate(0.5deg); }
}

@keyframes cat-head-nuzzle {
  0%, 100% { transform: translate(0) rotate(0) scale(1); }
  22% { transform: translate(1.5%, 0) rotate(0.8deg) scale(0.995, 1.008); }
  52% { transform: translate(-4.5%, 1%) rotate(-2.2deg) scale(1.018, 0.982); }
  76% { transform: translate(-2%, -0.5%) rotate(-0.7deg) scale(0.995, 1.01); }
}

@keyframes cat-belly-giggle {
  0%, 100% { transform: translateY(0) rotate(0) scale(1); }
  22% { transform: translateY(1.5%) rotate(-1.8deg) scale(1.025, 0.98); }
  42% { transform: translateY(-1%) rotate(2deg) scale(0.99, 1.025); }
  62% { transform: translateY(0.8%) rotate(-1.2deg) scale(1.015, 0.99); }
  80% { transform: translateY(-0.5%) rotate(0.7deg) scale(0.998, 1.008); }
}

@keyframes cat-paws-boop {
  0%, 100% { transform: translateY(0) rotate(0) scale(1); }
  28% { transform: translateY(2%) rotate(-0.8deg) scale(0.975, 1.02); }
  52% { transform: translateY(-4%) rotate(1deg) scale(1.04, 0.98); }
  74% { transform: translateY(-1%) rotate(-0.4deg) scale(0.995, 1.012); }
}

@keyframes cat-play-pounce {
  0%, 100% { transform: translate(0) rotate(0) scale(1); }
  14% { transform: translate(2%, 1%) rotate(1deg) scale(0.975, 1.025); }
  38% { transform: translate(-9%, 3%) rotate(-3deg) scale(1.04, 0.96); }
  56% { transform: translate(-6%, -2%) rotate(-1.2deg) scale(0.985, 1.025); }
  78% { transform: translate(-2%, 0) rotate(0.5deg) scale(1.01, 0.99); }
}

@keyframes cat-play-bat {
  0%, 100% { transform: translateY(0) rotate(0) scale(1); }
  16% { transform: translateY(2%) rotate(-1deg) scale(0.98, 1.02); }
  34% { transform: translateY(-6%) rotate(2deg) scale(1.04, 0.97); }
  52% { transform: translateY(-2%) rotate(-1.2deg) scale(0.99, 1.015); }
  72% { transform: translateY(-4%) rotate(0.8deg) scale(1.02, 0.985); }
}

@keyframes cat-play-cuddle {
  0%, 100% { transform: translate(0) scale(1); filter: brightness(1); }
  22% { transform: translate(-2%, 1%) scale(1.015, 0.985); }
  48% { transform: translate(-4%, 2%) scale(1.025, 0.975); filter: brightness(1.035); }
  72% { transform: translate(-2%, 1%) scale(0.995, 1.008); }
}

@keyframes cat-play-shadow {
  0%, 100% { opacity: 1; transform: translateX(0) scaleX(1); }
  42% { opacity: 0.72; transform: translateX(-5%) scaleX(1.08); }
  62% { opacity: 0.58; transform: translate(-3%, -2%) scaleX(0.88); }
}

@keyframes cat-yarn-pounce {
  0%, 100% {
    filter: drop-shadow(0 7px 6px rgb(57 70 112 / 15%));
    transform: translate(0) rotate(0) scale(1);
  }

  24% {
    filter: drop-shadow(0 10px 8px rgb(57 70 112 / 18%)) brightness(1.04);
    transform: translate(38%, -12%) rotate(22deg) scale(1.04);
  }

  52% {
    filter: drop-shadow(0 6px 5px rgb(57 70 112 / 16%)) brightness(1.02);
    transform: translate(78%, 5%) rotate(62deg) scale(0.97);
  }

  78% {
    filter: drop-shadow(0 9px 7px rgb(57 70 112 / 17%));
    transform: translate(34%, -6%) rotate(24deg) scale(1.015);
  }
}

@keyframes cat-yarn-bat {
  0%, 100% { transform: translate(0) rotate(0) scale(1); }
  18% { transform: translate(36%, -16%) rotate(20deg) scale(1.03); }
  38% { transform: translate(82%, -72%) rotate(72deg) scale(0.94); }
  58% { transform: translate(96%, -28%) rotate(118deg) scale(1.02); }
  76% { transform: translate(52%, -54%) rotate(164deg) scale(0.97); }
}

@keyframes cat-yarn-cuddle {
  0%, 100% { transform: translate(0) rotate(0) scale(1); }
  24% { transform: translate(42%, -8%) rotate(24deg) scale(1.02); }
  52% { transform: translate(92%, 4%) rotate(56deg) scale(0.92); }
  78% { transform: translate(76%, 1%) rotate(42deg) scale(0.96); }
}

@keyframes cat-purr-ring {
  0% { opacity: 0; transform: scale(0.45); }
  28% { opacity: 0.72; }
  100% { opacity: 0; transform: scale(1.45); }
}

@keyframes cat-loss-reaction {
  0%, 100% { transform: none; filter: none; }
  20% { transform: translateY(3px) rotate(-2deg); filter: saturate(0.72); }
  42% { transform: translateY(2px) rotate(1deg); filter: saturate(0.72); }
  72% { transform: translateY(2px); filter: saturate(0.78); }
}

.cat-pose-enter-active,
.cat-pose-leave-active,
.cat-sleep-mark-enter-active,
.cat-sleep-mark-leave-active {
  transition:
    opacity 180ms ease,
    transform 220ms var(--ease-out);
}

.cat-pose-enter-from {
  opacity: 0;
  transform: translateY(3px) scale(0.985);
}

.cat-pose-leave-to,
.cat-sleep-mark-enter-from,
.cat-sleep-mark-leave-to {
  opacity: 0;
}

.cat-sleep-mark-enter-from {
  transform: translate(-2px, 2px);
}

.cat-bubble-enter-active,
.cat-bubble-leave-active {
  transition: opacity 150ms ease, transform 180ms var(--ease-out);
}

.cat-bubble-enter-from,
.cat-bubble-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(3px) scale(0.96);
}

@media (max-width: 620px) {
  .cat-companion {
    width: var(--cat-companion-width, 118px);
    height: var(--cat-companion-height, 142px);

    &__yarn-trigger {
      bottom: 28%;
    }

    &__bubble {
      top: 10%;
      left: 52%;
      max-width: 96px;
      font-size: 11px;
    }
  }
}

@media (prefers-reduced-motion: reduce) {
  .cat-pose-enter-active,
  .cat-pose-leave-active,
  .cat-sleep-mark-enter-active,
  .cat-sleep-mark-leave-active,
  .cat-bubble-enter-active,
  .cat-bubble-leave-active {
    transition: none;
  }

  .cat-companion__image {
    animation: none !important;
  }

  .cat-companion__motion,
  .cat-companion__ground-shadow,
  .cat-companion__purr-ring,
  .cat-companion__yarn-trigger {
    animation: none !important;
  }

  .cat-companion[data-motion="feeding"] .cat-companion__motion {
    filter: brightness(1.06);
  }

  .cat-companion[data-motion="feeding"] .cat-companion__purr-ring--one {
    opacity: 0.58;
    transform: scale(0.76);
  }

  .cat-companion[data-motion="petting"] .cat-companion__purr-ring--one {
    opacity: 0.55;
    transform: scale(0.82);
  }

  .cat-companion[data-motion="curious"] .cat-companion__motion,
  .cat-companion[data-motion="petting"] .cat-companion__motion {
    filter: brightness(1.035);
  }

  .cat-companion[data-motion="playing"] .cat-companion__motion {
    filter: brightness(1.035);
  }

  .cat-companion[data-motion="playing"] .cat-companion__yarn-trigger {
    filter: drop-shadow(0 8px 7px rgb(57 70 112 / 18%)) brightness(1.04);
  }

  .cat-companion__yarn-trigger {
    transition: none;
  }

}
</style>
