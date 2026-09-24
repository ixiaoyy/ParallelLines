<script setup lang="ts">
import {
  AimOutlined, AppstoreOutlined, ArrowRightOutlined, BulbOutlined,
  ClockCircleFilled, CoffeeOutlined, FireFilled, HeartFilled,
  HeartOutlined, SearchOutlined, SmileOutlined, StarFilled, ThunderboltOutlined,
} from "@ant-design/icons-vue";
import { computed, ref } from "vue";

import type { CatalogProject } from "@/features/catalog/model";
import { useCatalog, useRateCatalogProject } from "@/features/catalog/queries";
import { cssUrl, staticAssetUrl } from "@/shared/assets/staticAssets";

type SortMode = "latest" | "hot";
type CatalogEntry = CatalogProject & { categorySlug: string };
const catalogAssetPath = "/catalog/2026-09-24-v1";
const heroBackground = cssUrl(staticAssetUrl(`${catalogAssetPath}/hero-sky.webp`));
const mascotUrl = staticAssetUrl(`${catalogAssetPath}/chibi-cat-explorer.webp`);
const seedOrder = new Map([
  "clock-out", "merge-watermelon", "qin-imperial-factory", "super-mario",
  "csgo-desert", "infinite-garden", "fruit-ninja", "qq-racing",
  "cf-transport", "pelican-bike", "fablespace", "generals-soldiers",
].map((slug, index) => [slug, index]));

const catalogQuery = useCatalog();
const ratingMutation = useRateCatalogProject();
const searchInput = ref("");
const search = ref("");
const selectedCategory = ref("all");
const sortMode = ref<SortMode>("latest");
const pendingProjectId = ref<string | null>(null);
const ratingErrorProjectId = ref<string | null>(null);
const hoveredProjectId = ref<string | null>(null);
const hoveredScore = ref(0);

// 空分类保留在后台供管理员维护，公开页仅展示有项目的分类。
const categories = computed(() => (catalogQuery.data.value ?? []).filter((category) => category.projects.length > 0));
const allProjects = computed<CatalogEntry[]>(() =>
  categories.value.flatMap((category) =>
    category.projects.map((project) => ({
      ...project,
      categorySlug: category.slug,
    })),
  ),
);
const normalizedSearch = computed(() => search.value.trim().toLocaleLowerCase());

// 分类、搜索与排序只改变展示，项目归属仍以后台数据为准。
const visibleProjects = computed(() => {
  const matching = allProjects.value.filter((project) => {
    if (selectedCategory.value !== "all" && project.categorySlug !== selectedCategory.value) return false;
    if (!normalizedSearch.value) return true;
    return [displayName(project), project.name, displayDescription(project), project.url]
      .some((value) => value.toLocaleLowerCase().includes(normalizedSearch.value));
  });
  return matching.sort((left, right) => {
    if (sortMode.value === "hot") {
      const qualified = Number(isHot(right)) - Number(isHot(left));
      if (qualified) return qualified;
      const ratings = right.ratingCount - left.ratingCount;
      if (ratings) return ratings;
      const average = (right.averageScore ?? 0) - (left.averageScore ?? 0);
      if (average) return average;
    }
    const created = Date.parse(right.createdAt) - Date.parse(left.createdAt);
    if (created) return created;
    return (seedOrder.get(left.slug) ?? Number.MAX_SAFE_INTEGER)
      - (seedOrder.get(right.slug) ?? Number.MAX_SAFE_INTEGER);
  });
});

// 朝花夕拾尚未开放；沿用原项目标识，兼容仍未执行分类迁移的环境。
function isComingSoon(project: CatalogProject): boolean {
  return project.slug === "fablespace";
}

function displayName(project: CatalogProject): string {
  return isComingSoon(project) ? "朝花夕拾" : project.name;
}

function displayDescription(project: CatalogProject): string {
  if (isComingSoon(project)) return "星露谷风格的田园生活，敬请期待。";
  if (project.description) return project.description;
  const introductions: Record<string, string> = {
    "clock-out": "解开难题，准点下班！",
    "merge-watermelon": "水果合成，挑战大西瓜。",
    "qin-imperial-factory": "开动奇妙工坊，快乐打螺丝。",
    "super-mario": "跳进蘑菇世界，快乐闯关。",
    "csgo-desert": "穿过沙漠，展开战术行动。",
    "infinite-garden": "在无尽庭院中，发现新的风景。",
    "fruit-ninja": "一刀划过，爽快切水果！",
    "qq-racing": "极速漂移，放肆飞驰！",
    "cf-transport": "经典地图，热血重燃！",
    "pelican-bike": "小鹈鹕也能骑向远方！",
    "generals-soldiers": "小兵也有大梦想！",
  };
  return introductions[project.slug] ?? "发现一个有趣的小世界，点开看看吧。";
}

// 首批项目使用专属封面，后台上传图片优先显示，新项目使用通用封面。
function coverUrl(project: CatalogProject): string {
  if (project.iconUrl) return project.iconUrl;
  const covers = new Set([
    "clock-out", "merge-watermelon", "qin-imperial-factory", "super-mario",
    "csgo-desert", "infinite-garden", "fruit-ninja", "qq-racing",
    "cf-transport", "pelican-bike", "fablespace", "generals-soldiers",
  ]);
  return staticAssetUrl(`${catalogAssetPath}/covers/${covers.has(project.slug) ? project.slug : "discover"}.webp`);
}

// 新项目和热门项目沿用已确定的 7 天、10 人与 4.5 分规则。
function isNew(project: CatalogProject): boolean {
  const elapsed = Date.now() - Date.parse(project.createdAt);
  return Number.isFinite(elapsed) && elapsed >= 0 && elapsed <= 7 * 24 * 60 * 60 * 1000;
}

function isHot(project: CatalogProject): boolean {
  return project.ratingCount >= 10 && (project.averageScore ?? 0) >= 4.5;
}

function isFilled(project: CatalogProject, score: number): boolean {
  const preview = hoveredProjectId.value === project.id ? hoveredScore.value : 0;
  return score <= (project.myScore ?? preview);
}

function previewScore(project: CatalogProject, score: number): void {
  if (project.myScore !== null || pendingProjectId.value !== null) return;
  hoveredProjectId.value = project.id;
  hoveredScore.value = score;
}

function clearPreview(): void {
  hoveredProjectId.value = null;
  hoveredScore.value = 0;
}

function submitSearch(): void {
  search.value = searchInput.value;
}

// 游客只提交首次评分；预告项目不开放评分。
async function rateProject(project: CatalogProject, score: number): Promise<void> {
  if (isComingSoon(project) || project.myScore !== null || pendingProjectId.value !== null) return;
  ratingErrorProjectId.value = null;
  pendingProjectId.value = project.id;
  clearPreview();
  try {
    await ratingMutation.mutateAsync({ projectId: project.id, score });
  } catch {
    ratingErrorProjectId.value = project.id;
  } finally {
    pendingProjectId.value = null;
  }
}
</script>

<template>
  <main class="catalog-page" aria-labelledby="catalog-title">
    <section class="catalog-hero" :style="{ '--catalog-hero-image': heroBackground }" aria-labelledby="catalog-title">
      <div class="catalog-page__wrap catalog-hero__inner">
        <header class="catalog-header">
          <RouterLink class="catalog-brand" to="/" aria-label="平行线首页">
            <img src="/logo-lines-mark.png" alt="" width="44" height="44" />
            <span>平行线</span>
          </RouterLink>
        </header>
        <div class="catalog-hero__copy">
          <p class="catalog-hero__eyebrow">发现有趣的项目</p>
          <h1 id="catalog-title">今天想玩点什么<span>？</span></h1>
          <p class="catalog-hero__intro">探索好玩的游戏，发现更多有趣的世界 <StarFilled aria-hidden="true" /></p>
          <form class="catalog-search" role="search" @submit.prevent="submitSearch">
            <SearchOutlined class="catalog-search__icon" aria-hidden="true" />
            <label class="catalog-search__label" for="catalog-query">搜索项目名称、介绍或网址</label>
            <input id="catalog-query" v-model="searchInput" type="search" placeholder="搜索项目名称、介绍或网址..." autocomplete="off" @search="submitSearch" />
            <button type="submit">搜索</button>
          </form>
        </div>
        <img class="catalog-hero__mascot" :src="mascotUrl" alt="" width="430" height="430" />
      </div>
    </section>

    <div class="catalog-page__wrap">
      <section class="catalog-list" aria-label="项目目录">
        <template v-if="catalogQuery.isLoading.value">
          <div class="catalog-state catalog-state--loading" role="status" aria-label="正在加载项目目录">
            <span class="catalog-state__spinner" aria-hidden="true"></span>
            <span>正在加载项目目录…</span>
          </div>
        </template>
        <div v-else-if="catalogQuery.isError.value" class="catalog-state" role="alert">
          <span>项目目录暂时不可用，请稍后重试。</span>
          <button type="button" @click="catalogQuery.refetch()">重新加载</button>
        </div>
        <template v-else>
          <div class="catalog-controls">
            <div class="catalog-categories" role="group" aria-label="项目分类">
              <button type="button" class="catalog-filter" :class="{ 'is-active': selectedCategory === 'all' }" :aria-pressed="selectedCategory === 'all'" @click="selectedCategory = 'all'">全部</button>
              <button v-for="category in categories" :key="category.id" type="button" class="catalog-filter" :class="{ 'is-active': selectedCategory === category.slug }" :aria-pressed="selectedCategory === category.slug" @click="selectedCategory = category.slug">
                <img v-if="category.iconUrl" :src="category.iconUrl" alt="" width="22" height="22" />
                <AimOutlined v-else-if="category.slug === 'shooting'" aria-hidden="true" />
                <ThunderboltOutlined v-else-if="category.slug === 'racing'" aria-hidden="true" />
                <SmileOutlined v-else-if="category.slug === 'funny'" aria-hidden="true" />
                <BulbOutlined v-else-if="category.slug === 'puzzle'" aria-hidden="true" />
                <CoffeeOutlined v-else-if="category.slug === 'casual'" aria-hidden="true" />
                <AppstoreOutlined v-else aria-hidden="true" />
                {{ category.name }}
              </button>
            </div>
            <div class="catalog-sort" role="group" aria-label="项目排序">
              <button type="button" :class="{ 'is-active': sortMode === 'latest' }" :aria-pressed="sortMode === 'latest'" @click="sortMode = 'latest'"><ClockCircleFilled aria-hidden="true" /> 最新</button>
              <button type="button" :class="{ 'is-active': sortMode === 'hot' }" :aria-pressed="sortMode === 'hot'" @click="sortMode = 'hot'"><FireFilled aria-hidden="true" /> 热门</button>
            </div>
          </div>
          <div class="catalog-results" role="status">{{ visibleProjects.length }} 个项目</div>

          <div v-if="visibleProjects.length === 0" class="catalog-state" role="status">
            <span>没有找到匹配的项目</span>
            <button v-if="search || selectedCategory !== 'all'" type="button" @click="search = ''; searchInput = ''; selectedCategory = 'all'">清除筛选</button>
          </div>
          <div v-else class="catalog-grid">
            <article v-for="project in visibleProjects" :key="project.id" class="catalog-card" :class="{ 'catalog-card--coming-soon': isComingSoon(project) }">
              <div class="catalog-card__media">
                <img :src="coverUrl(project)" :alt="`${displayName(project)}封面`" loading="lazy" />
                <div class="catalog-card__badges">
                  <span v-if="isNew(project)" class="catalog-card__badge catalog-card__badge--new" role="img" aria-label="新项目" title="新项目"><ClockCircleFilled aria-hidden="true" /></span>
                  <span v-if="isHot(project) && !isComingSoon(project)" class="catalog-card__badge catalog-card__badge--hot" role="img" aria-label="热门项目" title="热门项目"><FireFilled aria-hidden="true" /></span>
                </div>
              </div>
              <div class="catalog-card__body">
                <h2>{{ displayName(project) }}</h2>
                <p class="catalog-card__description">{{ displayDescription(project) }}</p>
                <div v-if="isComingSoon(project)" class="catalog-card__footer catalog-card__footer--coming-soon"><span>敬请期待</span><span>很快见面</span></div>
                <div v-else class="catalog-card__footer">
                  <div class="catalog-card__rating" :class="{ 'is-pending': pendingProjectId === project.id }">
                    <div class="catalog-card__hearts" role="group" :aria-label="`${displayName(project)}的评分`" @mouseleave="clearPreview">
                      <button v-for="score in 5" :key="score" type="button" :disabled="project.myScore !== null || pendingProjectId !== null" :aria-label="project.myScore === null ? `给${displayName(project)}评${score}分` : `${displayName(project)}已评${project.myScore}分，不能修改`" :title="project.myScore === null ? `评${score}分` : `已评${project.myScore}分`" @mouseenter="previewScore(project, score)" @focus="previewScore(project, score)" @blur="clearPreview" @click="rateProject(project, score)">
                        <HeartFilled v-if="isFilled(project, score)" aria-hidden="true" />
                        <HeartOutlined v-else aria-hidden="true" />
                      </button>
                    </div>
                    <span class="catalog-card__rating-count">{{ project.ratingCount }} 人评分</span>
                  </div>
                  <RouterLink v-if="project.kind === 'internal'" class="catalog-card__open" :to="project.url" :aria-label="`打开${displayName(project)}`"><ArrowRightOutlined aria-hidden="true" /></RouterLink>
                  <a v-else class="catalog-card__open" :href="project.url" target="_blank" rel="noopener noreferrer" :aria-label="`打开${displayName(project)}，在新窗口`"><ArrowRightOutlined aria-hidden="true" /></a>
                </div>
                <p v-if="ratingErrorProjectId === project.id" class="catalog-card__rating-error" role="alert">评分暂时不可用，请稍后重试。</p>
              </div>
            </article>
          </div>
          <p class="catalog-list__rating-note">每个项目每位访客只能评一次，提交后不可修改。</p>
        </template>
      </section>
      <footer class="catalog-footer">平行线 · 发现有趣的项目</footer>
    </div>
  </main>
</template>

<style scoped lang="scss" src="./CatalogHomePage.scss"></style>
