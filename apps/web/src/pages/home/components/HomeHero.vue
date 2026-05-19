<script setup lang="ts">
export interface CommunitySignal {
  label: string;
  value: string;
  helper: string;
}

const props = defineProps<{
  search: string;
  signals: CommunitySignal[];
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
        <p class="hero-lead">
          轻盈、安静的技术论坛——优先呈现最新讨论、热门话题与清晰分类，帮你快速找到值得参与的内容。
        </p>
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

      <div class="signal-card" aria-label="社区实时信号">
        <div class="signal-visual" aria-hidden="true">
          <img src="/parallel_convergence_graphic.png" alt="平行线交汇" class="hero-convergence-img" />
        </div>
        <div class="signal-caption">
          <div v-for="signal in signals" :key="signal.label">
            <strong>{{ signal.value }}</strong>
            <span>{{ signal.label }}</span>
            <small>{{ signal.helper }}</small>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped lang="scss" src="./HomeHero.scss"></style>
