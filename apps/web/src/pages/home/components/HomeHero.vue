<script setup lang="ts">
import HeroMeetVisual from "@/pages/home/components/HeroMeetVisual.vue";

const props = defineProps<{
  search: string;
}>();

const emit = defineEmits<{
  "update:search": [value: string];
  submitSearch: [];
}>();

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
        <form class="hero-search" role="search" aria-label="搜索平行线主题" @submit.prevent="emit('submitSearch')">
          <span aria-hidden="true">⌕</span>
          <input :value="props.search" type="search" placeholder="搜索主题、标签、成员" @input="updateSearch" />
          <button type="submit" :disabled="!props.search.trim()">搜索</button>
        </form>
        <div class="hero-cta">
          <RouterLink class="btn btn-primary" :to="{ name: 'new-topic' }">开始讨论</RouterLink>
          <RouterLink class="btn btn-secondary" :to="{ name: 'board-directory' }">浏览分类</RouterLink>
        </div>
      </div>

      <div class="signal-card" aria-label="平行线社区图示">
        <div class="signal-visual" aria-hidden="true">
          <HeroMeetVisual />
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped lang="scss" src="./HomeHero.scss"></style>
