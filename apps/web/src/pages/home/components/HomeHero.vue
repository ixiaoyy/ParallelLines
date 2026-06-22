<script setup lang="ts">
import { SearchOutlined } from "@ant-design/icons-vue";
import { defineAsyncComponent } from "vue";

import { useMediaQuery } from "@/shared/lib/useMediaQuery";

// Loads the decorative desktop/tablet hero visual only when it can actually be shown.
// Key parameters: none. Return value is the HeroMeetVisual component; side effect is deferred visual chunk loading.
const HeroMeetVisual = defineAsyncComponent(() => import("@/pages/home/components/HeroMeetVisual.vue"));

const props = defineProps<{
  search: string;
}>();

const emit = defineEmits<{
  "update:search": [value: string];
  submitSearch: [];
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
        <p class="hero-eyebrow">技术讨论 · 经验分享 · 项目共创</p>
        <h1 id="home-hero-title" class="hero-title">
          <span class="hero-title__line">让不同方向的思考，</span>
          <span class="hero-title__line"> 在<em class="hero-brand">平行线</em>上汇合。 </span>
        </h1>
        <form class="hero-search" role="search" aria-label="搜索首页主题" @submit.prevent="emit('submitSearch')">
          <label class="hero-search__field">
            <SearchOutlined aria-hidden="true" />
            <input :value="props.search" type="search" aria-label="搜索主题" @input="updateSearch" />
          </label>
          <button type="submit" :disabled="!props.search.trim()">搜索</button>
        </form>
        <div class="hero-cta">
          <RouterLink class="btn btn-primary" :to="{ name: 'new-topic' }">发布主题</RouterLink>
        </div>
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
