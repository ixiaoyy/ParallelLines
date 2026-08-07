<script setup lang="ts">
import { SearchOutlined, SlidersOutlined } from "@ant-design/icons-vue";
import { defineAsyncComponent } from "vue";

import { useMediaQuery } from "@/shared/lib/useMediaQuery";

// Loads the decorative desktop/tablet hero visual only when it can actually be shown.
// Key parameters: none. Return value is the HeroMeetVisual component; side effect is deferred visual chunk loading.
const HeroMeetVisual = defineAsyncComponent(() => import("@/pages/home/components/HeroMeetVisual.vue"));

const props = defineProps<{
  search: string;
  filtersOpen: boolean;
  hasActiveFilters: boolean;
}>();

const emit = defineEmits<{
  "update:search": [value: string];
  submitSearch: [];
  toggleFilters: [];
}>();

const shouldShowHeroVisual = useMediaQuery("(min-width: 561px)", true);

function updateSearch(event: Event) {
  emit("update:search", (event.target as HTMLInputElement).value);
}
</script>

<template>
  <section class="home-hero" aria-labelledby="home-hero-title">
    <div class="hero-grid">
      <div class="hero-copy">
        <p class="hero-eyebrow">ParallelLines · 技术讨论 · 经验分享 · 项目共创</p>
        <h1 id="home-hero-title" class="hero-title">
          <span class="hero-title__line">让不同方向的思考，</span>
          <span class="hero-title__line"> 在<em class="hero-brand">平行线</em>上汇合。 </span>
        </h1>
        <form class="hero-search" role="search" aria-label="搜索首页主题" @submit.prevent="emit('submitSearch')">
          <label class="hero-search__field">
            <SearchOutlined class="hero-search__search-icon" aria-hidden="true" />
            <input :value="props.search" type="search" placeholder="搜索" aria-label="搜索" @input="updateSearch" />
          </label>
          <button
            type="button"
            class="hero-filter-button"
            :class="{ active: props.filtersOpen, 'has-filters': props.hasActiveFilters }"
            :aria-pressed="props.filtersOpen"
            :aria-label="props.filtersOpen ? '收起筛选' : '展开筛选'"
            aria-controls="topic-feed-filters"
            @click="emit('toggleFilters')"
          >
            <SlidersOutlined aria-hidden="true" />
          </button>
        </form>
        <ul class="hero-proof" aria-label="社区能力">
          <li>让思考发光</li>
          <li>让善意回响</li>
          <li>让答案相遇</li>
        </ul>
      </div>

      <div v-if="shouldShowHeroVisual" class="signal-card" aria-label="平行线社区图示">
        <div class="signal-visual" aria-hidden="true">
          <HeroMeetVisual />
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped lang="scss" src="./HomeHero.scss"></style>
