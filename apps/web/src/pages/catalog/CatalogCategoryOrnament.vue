<script setup lang="ts">
import { computed, type CSSProperties } from "vue";
import type { CatalogCategoryVisual } from "@/features/catalog/categoryVisuals";

const props = defineProps<{ visual: CatalogCategoryVisual }>();
const artwork = computed(() => props.visual.artwork);
const cropStyle = computed<CSSProperties>(() => {
  const art = artwork.value;
  return {
    "--catalog-art-aspect": art?.kind === "atlas"
      ? String(art.bounds.width / art.bounds.height) : "2.5",
  };
});
const sourceStyle = computed<CSSProperties>(() => {
  const art = artwork.value;
  if (art?.kind !== "atlas") return {};
  const box = art.bounds;
  return {
    width: `${100 * art.sourceWidth / box.width}%`,
    height: `${100 * art.sourceHeight / box.height}%`,
    left: `${-100 * box.x / box.width}%`,
    top: `${-100 * box.y / box.height}%`,
  };
});
</script>

<template>
  <span v-if="artwork" class="catalog-category-art" :data-category-art="visual.key"
    :style="cropStyle" aria-hidden="true">
    <span class="catalog-category-art__crop">
      <img class="catalog-category-art__source" :class="{ 'catalog-category-art__source--image': artwork.kind === 'image' }"
        :src="artwork.src" :style="sourceStyle" alt="" draggable="false" loading="lazy" decoding="async" />
    </span>
  </span>
</template>

<style scoped lang="scss">
.catalog-category-art {
  // Follow the real artwork width so portrait figures do not leave a wide gap
  // before the title. Parent sections may set both dimensions without distortion.
  display: grid;
  width: min(var(--catalog-art-max-width, 145px), calc(var(--catalog-art-height, 64px) * var(--catalog-art-aspect)));
  height: var(--catalog-art-height, 64px);
  flex: 0 0 auto;
  place-items: end center;
  pointer-events: none;
}
.catalog-category-art__crop {
  position: relative;
  display: block;
  width: min(100%, calc(var(--catalog-art-height, 64px) * var(--catalog-art-aspect)));
  aspect-ratio: var(--catalog-art-aspect);
  overflow: hidden;
}
.catalog-category-art__source {
  position: absolute;
  display: block;
  max-width: none;
  object-fit: fill;
}
.catalog-category-art__source--image {
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
}
@media (max-width: 760px) {
  .catalog-category-art {
    width: min(var(--catalog-art-max-width, 100px), calc(var(--catalog-art-height, 48px) * var(--catalog-art-aspect)));
    height: var(--catalog-art-height, 48px);
  }
}
</style>
