<script setup lang="ts">
import { computed, type CSSProperties } from "vue";
import { categoryAccentFor } from "./catalogCategoryAccents";

const props = defineProps<{ slug: string; placement: "heading" | "card-corner" }>();
const accent = computed(() => categoryAccentFor(props.slug));
const aspect = computed(() => {
  const art = accent.value?.artwork;
  return art?.kind === "atlas" ? art.bounds.width / art.bounds.height : art?.aspectRatio ?? 1;
});
const imageStyle = computed<CSSProperties>(() => {
  const art = accent.value?.artwork;
  if (art?.kind !== "atlas") return {};
  const box = art.bounds;
  return { width: `${100 * art.sourceWidth / box.width}%`, height: `${100 * art.sourceHeight / box.height}%`, left: `${-100 * box.x / box.width}%`, top: `${-100 * box.y / box.height}%` };
});
</script>

<template>
  <span v-if="accent && accent.placement === placement" class="catalog-category-accent" :data-accent-kind="accent.kind" :style="{ '--accent-aspect': aspect }" aria-hidden="true">
    <span class="catalog-category-accent__crop"><img :src="accent.artwork.src" :style="imageStyle" :class="{ 'catalog-category-accent__image': accent.artwork.kind === 'image' }" alt="" draggable="false" loading="lazy" decoding="async" fetchpriority="low" /></span>
  </span>
</template>

<style scoped lang="scss">
.catalog-category-accent {
  display: block;
  flex: none;
  width: calc(var(--category-spark-size) * min(1, var(--accent-aspect)));
  pointer-events: none;
}
.catalog-category-accent__crop { position: relative; display: block; width: 100%; aspect-ratio: var(--accent-aspect); overflow: hidden; }
.catalog-category-accent img { position: absolute; display: block; max-width: none; }
.catalog-category-accent .catalog-category-accent__image { inset: 0; width: 100%; height: 100%; object-fit: contain; }
// 指南针保留在探索首张封面的角落，只覆住几个像素，不接管点击。
[data-accent-kind="compass"] {
  position: absolute;
  z-index: 3;
  top: calc(100% + 8px);
  left: 12px;
}
</style>
