<script setup lang="ts">
import { computed, type CSSProperties } from "vue";
import { microAccentsFor } from "./catalogMicroAccents";
const props = defineProps<{ slug: string }>();
const accents = computed(() => microAccentsFor(props.slug));
function placement(accent: ReturnType<typeof microAccentsFor>[number]): CSSProperties {
  const [, , width, height] = accent.sprite.box;
  return { "--micro-x": accent.x, "--micro-y": accent.y, "--micro-aspect": width / height,
    rotate: `${accent.rotation}deg` };
}
function crop(accent: ReturnType<typeof microAccentsFor>[number]): CSSProperties {
  const [x, y, width, height] = accent.sprite.box;
  return { width: `${100 * accent.sprite.sourceWidth / width}%`, height: `${100 * accent.sprite.sourceHeight / height}%`,
    left: `${-100 * x / width}%`, top: `${-100 * y / height}%` };
}
</script>

<template>
  <span v-if="accents.length" class="catalog-micro-accents" aria-hidden="true">
    <span v-for="(accent, index) in accents" :key="index" class="catalog-micro-accents__item" :data-micro-kind="accent.kind" :style="placement(accent)">
      <img :src="accent.sprite.src" :style="crop(accent)" alt="" loading="lazy" decoding="async" fetchpriority="low" draggable="false" />
    </span>
  </span>
</template>

<style scoped lang="scss">
.catalog-micro-accents { position: relative; align-self: stretch; flex: 1 0 28px; pointer-events: none; }
.catalog-micro-accents__item {
  position: absolute;
  top: var(--micro-y);
  left: var(--micro-x);
  display: block;
  width: calc(var(--category-spark-size) * min(1, var(--micro-aspect)));
  aspect-ratio: var(--micro-aspect);
  translate: -50% -50%;
  overflow: hidden;
  opacity: .75;
}
.catalog-micro-accents__item img { position: absolute; display: block; max-width: none; }
</style>
