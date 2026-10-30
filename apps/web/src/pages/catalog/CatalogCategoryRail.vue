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
  <div class="catalog-category-rail" :data-category-rail="slug" :data-composition="composition === 'mixed' && total < 3 ? 'balanced' : composition" :style="{ '--category-balanced-count': Math.max(1, Math.min(total, 3)) }" :class="{ 'catalog-category-rail--single': total === 1 }">
    <div ref="viewport" class="catalog-category-rail__viewport" :aria-label="`${name}游戏`" role="group" tabindex="0" @scroll.passive="measure" @keydown="handleKey">
      <slot />
    </div>
    <button v-if="canPrevious" class="catalog-category-rail__arrow catalog-category-rail__arrow--previous" type="button" :aria-label="`上一组${name}游戏`" @click="move(-1)"><LeftOutlined aria-hidden="true" /></button>
    <button v-if="canNext" class="catalog-category-rail__arrow catalog-category-rail__arrow--next" type="button" :aria-label="`下一组${name}游戏`" @click="move(1)"><RightOutlined aria-hidden="true" /></button>
  </div>
</template>

<style scoped lang="scss">
.catalog-category-rail { position: relative; min-width: 0; }
.catalog-category-rail__viewport {
  display: flex; align-items: stretch; gap: var(--category-card-gap, 10px);
  overflow-x: auto; overscroll-behavior-inline: contain; scrollbar-width: none;
  scroll-snap-type: x mandatory; scroll-padding-inline: 1px;
  border-radius: var(--catalog-card-radius, 22px);
}
.catalog-category-rail__viewport::-webkit-scrollbar { display: none; }
.catalog-category-rail[data-composition="mixed"] .catalog-category-rail__viewport { overflow-anchor: none; scroll-snap-type: none; }
.catalog-category-rail__viewport > :deep(.catalog-card) {
  width: var(--category-card-width, calc((100% - 20px) / 3));
  min-width: 0; height: var(--category-card-height, 220px); flex: 0 0 auto;
  aspect-ratio: auto; scroll-snap-align: start;
}
.catalog-category-rail__viewport > :deep(.catalog-card:first-child) { width: var(--category-first-card-width, var(--category-card-width, calc((100% - 20px) / 3))); }
@media (min-width: 761px) {
  // An actual portrait card, not a wide card clipped by the carousel edge.
  .catalog-category-rail[data-composition="mixed"] { margin-top: -10px; }
  .catalog-category-rail[data-composition="mixed"] .catalog-category-rail__viewport { height: calc(var(--category-card-height, 220px) + 10px); align-items: flex-end; }
  // Portrait posters keep the complete artwork; landscape cards retain normal focal cropping.
  .catalog-category-rail[data-composition="mixed"] :deep(.catalog-card[data-cover-format="portrait"] .catalog-card__cover img) { object-fit: contain; }
  .catalog-category-rail[data-composition="mixed"] .catalog-category-rail__viewport > :deep(.catalog-card:nth-child(3n + 1)) { width: calc((100% - 20px) * .452631579); }
  .catalog-category-rail[data-composition="mixed"] .catalog-category-rail__viewport > :deep(.catalog-card:nth-child(3n + 2)) { width: calc((100% - 20px) * .347368421); }
  .catalog-category-rail[data-composition="mixed"] .catalog-category-rail__viewport > :deep(.catalog-card:nth-child(3n)) { width: calc((100% - 20px) * .2); height: calc(var(--category-card-height, 220px) + 10px); }
  .catalog-category-rail[data-composition="balanced"] .catalog-category-rail__viewport > :deep(.catalog-card) { width: calc((100% - (var(--category-balanced-count) - 1) * 10px) / var(--category-balanced-count)); }
  .catalog-category-rail[data-composition="panorama"] .catalog-category-rail__viewport > :deep(.catalog-card) { width: 100%; height: var(--category-single-height, 220px); }
}
.catalog-category-rail--single .catalog-category-rail__viewport > :deep(.catalog-card) { width: 100%; height: var(--category-single-height, 185px); }
.catalog-category-rail__arrow {
  position: absolute; z-index: 4; top: 50%; display: grid; width: 44px; height: 44px;
  place-items: center; transform: translateY(-50%); border: 1px solid #ffffff9c;
  border-radius: 50%; color: #fff; background: #505a54ce; font-size: 22px; cursor: pointer;
}
.catalog-category-rail__arrow:hover { background: #315f4e; }
.catalog-category-rail__arrow--next { right: -9px; }
.catalog-category-rail__arrow--previous { left: -9px; }
@media (max-width: 760px) {
  .catalog-category-rail { --category-card-width: 76%; --category-first-card-width: 76%; --category-card-height: auto; --category-single-height: auto; }
  .catalog-category-rail__viewport { gap: 10px; }
  .catalog-category-rail__viewport > :deep(.catalog-card) { height: auto; aspect-ratio: auto; }
  .catalog-category-rail__arrow { width: 44px; height: 44px; font-size: 18px; }
  .catalog-category-rail__arrow--next { right: -7px; }
  .catalog-category-rail__arrow--previous { left: -7px; }
}
</style>
