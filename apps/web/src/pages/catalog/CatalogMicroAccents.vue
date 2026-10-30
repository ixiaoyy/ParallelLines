<script setup lang="ts">
import { computed, type CSSProperties } from "vue";
import { microAccentsFor } from "./catalogMicroAccents";
const props = defineProps<{ slug: string }>();
const accents = computed(() => microAccentsFor(props.slug));
function placement(accent: ReturnType<typeof microAccentsFor>[number]): CSSProperties {
  const [, , width, height] = accent.sprite.box;
  return { "--micro-left": accent.left ?? "auto", "--micro-right": accent.right ?? "auto", "--micro-top": accent.top ?? "auto", "--micro-bottom": accent.bottom ?? "auto",
    width: `${accent.sprite.width}px`, aspectRatio: `${width} / ${height}`,
    transform: `rotate(${accent.rotation}deg)`, "--micro-mobile-left": accent.mobileLeft, "--micro-mobile-bottom": accent.mobileBottom };
}
function crop(accent: ReturnType<typeof microAccentsFor>[number]): CSSProperties {
  const [x, y, width, height] = accent.sprite.box;
  return { width: `${100 * accent.sprite.sourceWidth / width}%`, height: `${100 * accent.sprite.sourceHeight / height}%`,
    left: `${-100 * x / width}%`, top: `${-100 * y / height}%` };
}
</script>

<template>
  <span class="catalog-micro-accents" aria-hidden="true">
    <span v-for="(accent, index) in accents" :key="index" class="catalog-micro-accents__item" :data-micro-kind="accent.kind" :style="placement(accent)">
      <img :src="accent.sprite.src" :style="crop(accent)" alt="" loading="lazy" decoding="async" draggable="false" />
    </span>
  </span>
</template>

<style scoped lang="scss">
.catalog-micro-accents { position: absolute; inset: 0; z-index: 1; pointer-events: none; }
.catalog-micro-accents__item { position: absolute; display: block; overflow: hidden; opacity: .8; pointer-events: none; left: var(--micro-left); right: var(--micro-right); top: var(--micro-top); bottom: var(--micro-bottom); }
.catalog-micro-accents__item img { position: absolute; display: block; max-width: none; }
@media (max-width: 760px) {
  .catalog-micro-accents__item { left: var(--micro-mobile-left); right: auto; top: auto; bottom: var(--micro-mobile-bottom); }
  .catalog-micro-accents__item:nth-child(n + 3) { display: none; }
}
</style>
