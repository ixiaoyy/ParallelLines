<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, onUpdated, ref } from "vue";
import { LeftOutlined, RightOutlined } from "@ant-design/icons-vue";
import type { CatalogCategoryComposition } from "./catalogCategoryThemes";

defineProps<{ name: string; slug: string; total: number; composition?: CatalogCategoryComposition }>();
const viewport = ref<HTMLElement | null>(null);
const canPrevious = ref(false);
const canNext = ref(false);
let observer: ResizeObserver | undefined;

function measure(): void {
  const rail = viewport.value;
  if (!rail) return;
  canPrevious.value = rail.scrollLeft > 2;
  canNext.value = rail.scrollWidth - rail.clientWidth - rail.scrollLeft > 2;
}

function move(direction: number): void {
  const rail = viewport.value;
  if (!rail) return;
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  rail.scrollBy({ left: direction * rail.clientWidth * .85, behavior: reduced ? "instant" : "smooth" });
}

function handleKey(event: KeyboardEvent): void {
  // Standard link/button keys remain native; never capture document/game keys.
  if (event.target !== event.currentTarget || !["ArrowLeft", "ArrowRight"].includes(event.key)) return;
  event.preventDefault();
  move(event.key === "ArrowRight" ? 1 : -1);
}

onMounted(() => {
  observer = new ResizeObserver(measure);
  if (viewport.value) observer.observe(viewport.value);
  measure();
});
onUpdated(() => { void nextTick(measure); });
onUnmounted(() => observer?.disconnect());
</script>

<template>
  <div class="catalog-category-rail" :data-category-rail="slug" :data-composition="composition" :class="{ 'catalog-category-rail--single': total === 1 }">
    <div ref="viewport" class="catalog-category-rail__viewport" :aria-label="`${name}游戏`" role="group" tabindex="0" @scroll.passive="measure" @keydown="handleKey">
      <slot />
    </div>
    <button v-if="canPrevious" class="catalog-category-rail__arrow catalog-category-rail__arrow--previous" type="button" :aria-label="`上一组${name}游戏`" @click="move(-1)"><LeftOutlined aria-hidden="true" /></button>
    <button v-if="canNext" class="catalog-category-rail__arrow catalog-category-rail__arrow--next" type="button" :aria-label="`下一组${name}游戏`" @click="move(1)"><RightOutlined aria-hidden="true" /></button>
  </div>
</template>

<style scoped lang="scss">
.catalog-category-rail {
  --category-columns: 2;
  --category-rail-gap: 4px;
  --category-rail-peek: 20px;
  --category-tile-width: min(220px, calc((100cqw - var(--category-rail-peek) - var(--category-rail-gap) * var(--category-columns)) / var(--category-columns)));
  --category-tile-height: calc(var(--category-tile-width) * 4 / 7);
  position: relative;
  min-width: 0;
  container-type: inline-size;
}
// 1000/1200 are measured CrazyGames transitions. The other thresholds are
// ParallelLines adaptations, checked against our own container and sidebar.
@media (min-width: 600px) { .catalog-category-rail { --category-columns: 3; } }
@media (min-width: 800px) { .catalog-category-rail { --category-columns: 4; } }
@media (min-width: 1000px) { .catalog-category-rail { --category-columns: 5; } }
@media (min-width: 1200px) { .catalog-category-rail { --category-columns: 6; } }
@media (min-width: 1400px) { .catalog-category-rail { --category-columns: 7; } }
@media (min-width: 1600px) { .catalog-category-rail { --category-columns: 8; } }
@media (min-width: 1800px) { .catalog-category-rail { --category-columns: 9; } }
.catalog-category-rail__viewport {
  display: flex; align-items: flex-end; gap: var(--category-rail-gap);
  overflow-x: auto; overscroll-behavior-inline: contain; scrollbar-width: none;
  scroll-snap-type: x mandatory; scroll-padding-inline: 1px;
  border-radius: var(--catalog-card-radius, 22px);
}
.catalog-category-rail__viewport::-webkit-scrollbar { display: none; }
.catalog-category-rail[data-composition="mixed"] .catalog-category-rail__viewport { overflow-anchor: none; scroll-snap-type: none; }
.catalog-category-rail__viewport > :deep(.catalog-card) {
  width: var(--category-tile-width);
  min-width: 0; height: var(--category-tile-height); flex: 0 0 auto;
  aspect-ratio: auto; scroll-snap-align: start;
}
.catalog-category-rail[data-composition="mixed"] :deep(.catalog-card[data-cover-format="portrait"] .catalog-card__cover img),
.catalog-category-rail[data-composition="panorama"] :deep(.catalog-card__cover img) { object-fit: contain; }
.catalog-category-rail[data-composition="panorama"] .catalog-category-rail__viewport > :deep(.catalog-card) {
  width: min(100cqw, var(--category-single-max-width, 340px), calc(var(--category-tile-width) * 1.6));
  height: auto;
  aspect-ratio: 7 / 4;
}
@media (min-width: 761px) {
  // One modest lead, not a repeated percentage-based page filling pattern.
  .catalog-category-rail:not([data-composition="balanced"]):not([data-composition="panorama"]) .catalog-category-rail__viewport > :deep(.catalog-card:first-child:not([data-cover-format="portrait"])) {
    width: min(300px, calc(var(--category-tile-width) * var(--category-lead-scale, 1)));
    height: calc(var(--category-tile-height) * var(--category-lead-height-scale, 1));
  }
  // Portrait placement follows the measured source format, never a card index.
  .catalog-category-rail[data-composition="mixed"] .catalog-category-rail__viewport > :deep(.catalog-card[data-cover-format="portrait"]) {
    width: calc(var(--category-tile-height) * .85);
    height: calc(var(--category-tile-height) * 1.35);
  }
}
.catalog-category-rail__arrow {
  position: absolute; z-index: 4; top: 50%; display: grid; width: 44px; height: 44px;
  place-items: center; transform: translateY(-50%); border: 1px solid #ffffff9c;
  border-radius: 50%; color: #fff; background: #505a54ce; font-size: 22px; cursor: pointer;
}
.catalog-category-rail__arrow:hover { background: #315f4e; }
.catalog-category-rail__arrow--next { right: -9px; }
.catalog-category-rail__arrow--previous { left: -9px; }
@media (max-width: 760px) {
  .catalog-category-rail__viewport > :deep(.catalog-card) { height: auto; aspect-ratio: auto; }
  .catalog-category-rail :deep(.catalog-card__cover) { aspect-ratio: 7 / 4; }
  .catalog-category-rail[data-composition="mixed"] .catalog-category-rail__viewport > :deep(.catalog-card[data-cover-format="portrait"]) { width: max(44px, calc(var(--category-tile-height) * 17 / 27)); }
  .catalog-category-rail[data-composition="mixed"] :deep(.catalog-card[data-cover-format="portrait"] .catalog-card__cover) { aspect-ratio: 17 / 27; }
  .catalog-category-rail[data-composition="panorama"] .catalog-category-rail__viewport > :deep(.catalog-card) { aspect-ratio: auto; }
  .catalog-category-rail__arrow { width: 44px; height: 44px; font-size: 18px; }
  .catalog-category-rail__arrow--next { right: -7px; }
  .catalog-category-rail__arrow--previous { left: -7px; }
}
</style>
