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
    <span class="catalog-category-accent__crop"><img :src="accent.artwork.src" :style="imageStyle" :class="{ 'catalog-category-accent__image': accent.artwork.kind === 'image' }" alt="" draggable="false" loading="lazy" decoding="async" /></span>
    <span v-if="accent.caption" class="catalog-category-accent__caption">{{ accent.caption }}</span>
  </span>
</template>

<style scoped lang="scss">
.catalog-category-accent { position: absolute; z-index: 4; display: block; width: min(var(--accent-width), calc(var(--accent-max-height) * var(--accent-aspect))); pointer-events: none; }
.catalog-category-accent__crop { position: relative; display: block; width: 100%; aspect-ratio: var(--accent-aspect); overflow: hidden; }
.catalog-category-accent img { position: absolute; display: block; max-width: none; }
.catalog-category-accent .catalog-category-accent__image { inset: 0; width: 100%; height: 100%; object-fit: contain; }
.catalog-category-accent__caption { position: absolute; color: #914330; font: 700 12px / 1.4 var(--catalog-heading-font); letter-spacing: 2px; white-space: nowrap; }
[data-accent-kind="leaves"] { --accent-width: 170px; --accent-max-height: 58px; right: 110px; top: 13px; }
[data-accent-kind="branch-paper"] { --accent-width: 180px; --accent-max-height: 110px; right: 4px; top: 8px; }
[data-accent-kind="branch-paper"] .catalog-category-accent__caption { right: 9px; top: 50%; writing-mode: vertical-rl; }
[data-accent-kind="compass"] { --accent-width: 50px; --accent-max-height: 60px; left: 23px; top: calc(var(--category-heading-space, var(--category-heading-height)) - 11px); }
[data-accent-kind="compass"] .catalog-category-accent__caption { left: calc(100% + 5px); top: 7px; }
@media (max-width: 760px) {
  [data-accent-kind="leaves"] { --accent-width: 110px; --accent-max-height: 38px; left: 60px; right: auto; top: 1px; }
  [data-accent-kind="branch-paper"] { --accent-width: 100px; --accent-max-height: 70px; top: 26px; }
  [data-accent-kind="branch-paper"] .catalog-category-accent__caption { display: none; }
  [data-accent-kind="compass"] { --accent-width: 36px; --accent-max-height: 44px; left: 16px; }
  [data-accent-kind="compass"] .catalog-category-accent__caption { font-size: 10px; letter-spacing: 1px; }
}
</style>
