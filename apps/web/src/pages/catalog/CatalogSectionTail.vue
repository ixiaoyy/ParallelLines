<script setup lang="ts">
import { computed, type CSSProperties } from "vue";

import { staticAssetUrl } from "@/shared/assets/staticAssets";
import type { CategoryVisualKey } from "@/features/catalog/categoryVisuals";
import { categorySectionThemeFor } from "./catalogCategoryThemes";

const props = defineProps<{ slug: string }>();
const artByCategory = {
  action: { file: "story-tails-a.png", crop: [39, 57, 977, 242] },
  shooting: { file: "story-tails-a.png", crop: [33, 335, 983, 273] },
  racing: { file: "story-tails-a.png", crop: [30, 656, 984, 266] },
  stages: { file: "story-tails-a.png", crop: [50, 941, 966, 296] },
  puzzle: { file: "story-tails-a.png", crop: [208, 1258, 806, 262] },
  rts: { file: "story-tails-b.png", crop: [19, 125, 971, 184] },
  "tower-defense": { file: "story-tails-b.png", crop: [29, 341, 975, 303] },
  cards: { file: "story-tails-b.png", crop: [24, 682, 979, 239] },
  rpg: { file: "story-tails-b.png", crop: [22, 973, 977, 229] },
  simulation: { file: "story-tails-b.png", crop: [21, 1253, 981, 244] },
  casual: { file: "story-tails-c.png", crop: [31, 64, 988, 264] },
  romance: { file: "story-tails-c.png", crop: [184, 398, 825, 228] },
  horror: { file: "story-tails-c.png", crop: [195, 649, 823, 244] },
  exploration: { file: "story-tails-c.png", crop: [69, 958, 944, 252] },
  farming: { file: "story-tails-c.png", crop: [150, 1234, 866, 266] },
} as const satisfies Readonly<Record<CategoryVisualKey, { file: string; crop: readonly [number, number, number, number] }>>;
const art = computed(() => {
  const key = categorySectionThemeFor(props.slug).tail;
  return key ? artByCategory[key] : null;
});
const cropStyle = computed<CSSProperties>(() => art.value ? {
  aspectRatio: String(art.value.crop[2] / art.value.crop[3]),
  width: `min(21%, 220px, ${52 * art.value.crop[2] / art.value.crop[3]}px)`,
  height: "auto",
} : {});
const sourceStyle = computed<CSSProperties>(() => {
  if (!art.value) return {};
  const [x, y, width, height] = art.value.crop;
  return {
    width: `${100 * 1024 / width}%`,
    height: `${100 * 1536 / height}%`,
    left: `${-100 * x / width}%`,
    top: `${-100 * y / height}%`,
  };
});
</script>

<template>
  <span v-if="art" class="catalog-group__tail catalog-section-tail" :style="cropStyle" aria-hidden="true">
    <img :src="staticAssetUrl(`/catalog/2026-10-29-ui/${art.file}`)" :style="sourceStyle" alt="" draggable="false" loading="lazy" decoding="async" />
  </span>
</template>

<style scoped>
.catalog-section-tail { display: block; overflow: hidden; opacity: .68; }
.catalog-section-tail img { position: absolute; display: block; max-width: none; }
</style>
