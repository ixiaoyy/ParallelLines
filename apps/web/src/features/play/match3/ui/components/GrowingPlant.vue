<script setup lang="ts">
import { computed } from "vue";

import foliageUrl from "../assets/ambient/plant-foliage.webp";
import floweringUrl from "../assets/ambient/plant-flowering.webp";
import fruitingUrl from "../assets/ambient/plant-fruiting.webp";
import matureUrl from "../assets/ambient/plant-mature.webp";
import potUrl from "../assets/ambient/plant-pot.webp";
import {
  getGrowthPercent,
  getPlantStage,
  getPlantStagePresentation,
  type PlantStage,
} from "../game-ui";

const props = defineProps<{
  clearCount: number;
  ageDays: number;
  celebrating: boolean;
}>();
const growth = computed(() => getGrowthPercent(props.clearCount));
const plantScale = computed(() => 0.82 + growth.value * 0.0018);
const stage = computed(() => getPlantStage(props.clearCount, props.ageDays));
const stagePresentation = computed(() => getPlantStagePresentation(stage.value));
const stageAssets: Readonly<Record<PlantStage, string>> = {
  growing: foliageUrl,
  flowering: floweringUrl,
  fruiting: fruitingUrl,
  mature: matureUrl,
};
</script>

<template>
  <figure
    class="growing-plant"
    :class="{
      'growing-plant--celebrating': celebrating,
      'growing-plant--empty': clearCount === 0,
    }"
    :data-stage="stage"
    :style="{ '--growth': `${growth}%`, '--plant-scale': plantScale }"
    :aria-label="stagePresentation.label"
  >
    <img
      :key="stage"
      class="growing-plant__foliage"
      :src="stageAssets[stage]"
      alt=""
      width="512"
      height="512"
    />
    <img class="growing-plant__pot" :src="potUrl" alt="" width="512" height="512" />
    <span class="growing-plant__stage-mark" aria-hidden="true">
      <Transition name="stage-flower" mode="out-in">
        <img
          :key="stage"
          class="growing-plant__stage-flower"
          :src="stagePresentation.assetUrl"
          alt=""
          width="512"
          height="512"
        />
      </Transition>
    </span>
    <Transition name="growth-cue">
      <figcaption
        v-if="celebrating"
        class="growing-plant__growth-cue"
        aria-hidden="true"
      >
        植物 +1 成长
      </figcaption>
    </Transition>
  </figure>
</template>

<style scoped lang="scss">
.growing-plant {
  position: absolute;
  z-index: 4;
  right: var(--plant-right, clamp(24px, 5vw, 76px));
  bottom: var(--scene-plant-base, 260px);
  width: var(--plant-width, clamp(196px, 20vw, 286px));
  height: var(--plant-height, clamp(258px, 27vw, 372px));
  margin: 0;
  pointer-events: none;
  transform-origin: 50% 100%;

  &__foliage,
  &__pot {
    position: absolute;
    width: 100%;
    height: auto;
    object-fit: contain;
    user-select: none;
  }

  &__foliage {
    z-index: 1;
    right: 0;
    bottom: 48px;
    opacity: 1;
    transform: scale(var(--plant-scale));
    transform-origin: 50% 100%;
    transition:
      clip-path 620ms var(--ease-out),
      filter 320ms ease,
      opacity 420ms ease,
      transform 620ms var(--ease-out);
  }

  &[data-stage="growing"] &__foliage {
    clip-path: inset(calc(100% - var(--growth)) 0 0 0);
  }

  &[data-stage="growing"] &__stage-mark {
    top: auto;
    bottom: 55%;
    left: 50%;
    width: clamp(156px, 13vw, 196px);
    transform: translateX(-50%);
  }

  &[data-stage="growing"] &__stage-flower {
    width: 82%;
  }

  &__pot {
    z-index: 2;
    right: 3%;
    bottom: 0;
    width: 94%;
  }

  &__stage-mark {
    position: absolute;
    z-index: 3;
    top: 18px;
    left: -10px;
    width: clamp(54px, 5.2vw, 68px);
    aspect-ratio: 1;
    filter: drop-shadow(0 4px 5px rgb(59 70 88 / 20%));
  }

  &__stage-flower {
    position: absolute;
    right: 0;
    bottom: 0;
    left: 0;
    display: block;
    width: 48%;
    height: auto;
    margin: auto;
    object-fit: contain;
    transform-origin: 50% 82%;
    user-select: none;
  }

  &[data-stage="flowering"] &__stage-flower {
    width: 66%;
  }

  &[data-stage="fruiting"] &__stage-flower {
    width: 82%;
  }

  &[data-stage="mature"] &__stage-flower {
    width: 100%;
  }

  &--empty &__foliage {
    opacity: 0;
  }

  &--celebrating {
    animation: plant-reward 560ms var(--ease-out);
  }

  &--celebrating &__foliage {
    filter:
      brightness(1.08)
      drop-shadow(0 9px 14px rgb(129 107 177 / 18%));
  }

  &__growth-cue {
    position: absolute;
    z-index: 5;
    top: 14%;
    left: 50%;
    width: max-content;
    padding: 7px 10px;
    border-radius: 999px;
    color: #4b5268;
    background: rgb(255 251 229 / 94%);
    box-shadow: 0 9px 22px rgb(79 70 109 / 17%);
    font-size: clamp(12px, 1vw, 14px);
    font-weight: 780;
    line-height: 1;
    transform: translateX(-50%);
  }
}

.growth-cue-enter-active,
.growth-cue-leave-active {
  transition:
    opacity 180ms ease,
    filter 220ms ease,
    transform 260ms var(--ease-out);
}

.growth-cue-enter-from,
.growth-cue-leave-to {
  opacity: 0;
  filter: blur(2px);
  transform: translateX(-50%) translateY(7px);
}

.stage-flower-enter-active,
.stage-flower-leave-active {
  transition:
    opacity 220ms ease,
    transform 280ms var(--ease-out);
}

.stage-flower-enter-from {
  opacity: 0;
  transform: translateY(4px) scale(0.84);
}

.stage-flower-leave-to {
  opacity: 0;
  transform: translateY(-2px) scale(0.94);
}

@keyframes plant-reward {
  52% { transform: translateY(-7px) scale(1.045); }
}

@media (max-width: 620px) {
  .growing-plant {
    right: var(--plant-right, 4px);
    bottom: var(--scene-plant-base, 110px);
    width: var(--plant-width, 108px);
    height: var(--plant-height, 166px);
    opacity: 0.96;

    &__stage-mark {
      top: 14px;
      left: -4px;
      width: 54px;
    }

    &[data-stage="growing"] .growing-plant__stage-mark {
      top: auto;
      bottom: 45%;
      left: 50%;
      width: 92px;
      transform: translateX(-50%);
    }

    &[data-stage="growing"] .growing-plant__stage-flower {
      width: 82%;
    }
  }
}

@media (prefers-reduced-motion: reduce) {
  .growing-plant--celebrating {
    animation: none;
    filter: brightness(1.07);
  }

  .growing-plant__foliage {
    transition: none;
  }

  .stage-flower-enter-active,
  .stage-flower-leave-active,
  .growth-cue-enter-active,
  .growth-cue-leave-active {
    transition: none;
  }
}
</style>
