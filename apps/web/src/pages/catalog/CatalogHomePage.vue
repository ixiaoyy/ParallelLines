<script setup lang="ts">
import {
  AimOutlined, AppstoreOutlined, ArrowRightOutlined, BulbOutlined,
  ClockCircleFilled, CoffeeOutlined, FireFilled, HeartFilled,
  HeartOutlined, HourglassOutlined, SearchOutlined, SmileOutlined, StarFilled, ThunderboltOutlined,
} from "@ant-design/icons-vue";
import { computed, nextTick, ref, watch } from "vue";

import type { CatalogProject } from "@/features/catalog/model";
import { useCatalog, useRateCatalogProject } from "@/features/catalog/queries";
import { cssUrl, staticAssetUrl } from "@/shared/assets/staticAssets";

type SortMode = "latest" | "hot";
type CatalogEntry = CatalogProject & { categorySlug: string };
const PAGE_SIZE = 24;
const COMING_SOON_FILTER = "coming-soon";
const catalogAssetPath = "/catalog/2026-09-24-v1";
const newCatalogAssetPath = "/catalog/2026-09-25-v1";
const heroBackground = cssUrl(staticAssetUrl(`${catalogAssetPath}/hero-sky.webp`));
const mascotUrl = staticAssetUrl(`${catalogAssetPath}/chibi-cat-explorer.webp`);
const originalCoverSlugs = new Set([
  "clock-out", "merge-watermelon", "qin-imperial-factory", "super-mario",
  "csgo-desert", "infinite-garden", "fruit-ninja", "qq-racing",
  "cf-transport", "pelican-bike", "fablespace", "generals-soldiers",
]);
const newCoverSlugs = new Set([
  "yu-gi-oh-destiny-duel", "secondhand-3c-store", "voxel-tides", "sneaky-thief",
  "liuxin-watermelon", "xing-lei-shou-wei", "yongyao-crystal-tower",
  "zhi-guai-lu", "sanguo-zhengshi", "yeyu-tanglou", "non-euclidean-lab",
  "geodesic-explorer", "hyperbolic-room", "encounter-command-console",
]);
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
const visibleLimit = ref(PAGE_SIZE);
const pendingProjectId = ref<string | null>(null);
const ratingErrorProjectId = ref<string | null>(null);
const hoveredProjectId = ref<string | null>(null);
const hoveredScore = ref(0);
const authorDialog = ref<HTMLDialogElement | null>(null);
const selectedAuthor = ref<string | null>(null);

// 预告项目单独筛选，普通分类只展示已开放项目；后台归属保持原样。
const allCategories = computed(() => catalogQuery.data.value ?? []);
const categories = computed(() => allCategories.value.filter((category) =>
  category.projects.some((project) => !isComingSoon(project)),
));
const allProjects = computed<CatalogEntry[]>(() =>
  allCategories.value.flatMap((category) =>
    category.projects.map((project) => ({
      ...project,
      categorySlug: category.slug,
    })),
  ),
);
const hasComingSoon = computed(() => allProjects.value.some(isComingSoon));
const selectedAuthorProjects = computed(() =>
  allProjects.value.filter((project) => project.authorName === selectedAuthor.value),
);
const normalizedSearch = computed(() => search.value.trim().toLocaleLowerCase());

// 分类与排序只改变展示，查询词仅匹配卡片展示名称；项目归属仍以后台数据为准。
const visibleProjects = computed(() => {
  const matching = allProjects.value.filter((project) => {
    if (selectedCategory.value === COMING_SOON_FILTER) {
      if (!isComingSoon(project)) return false;
    } else {
      if (isComingSoon(project)) return false;
      if (selectedCategory.value !== "all" && project.categorySlug !== selectedCategory.value) return false;
    }
    if (!normalizedSearch.value) return true;
    return displayName(project).toLocaleLowerCase().includes(normalizedSearch.value);
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

// 大目录只先渲染首批卡片；筛选变化后重新从首批展示，搜索仍覆盖全部项目。
const displayedProjects = computed(() => visibleProjects.value.slice(0, visibleLimit.value));
watch([normalizedSearch, selectedCategory, sortMode], () => {
  visibleLimit.value = PAGE_SIZE;
});

function loadMoreProjects(): void {
  visibleLimit.value += PAGE_SIZE;
}

// 朝花夕拾尚未开放；沿用原项目标识，兼容仍未执行分类迁移的环境。
function isComingSoon(project: CatalogProject): boolean {
  return project.slug === "fablespace";
}

// 站内游戏与朝花夕拾统一展示原创署名，不用网址或后台空值推断具体作者。
function isOriginalProject(project: CatalogProject): boolean {
  return project.kind === "internal" || project.slug === "fablespace";
}

function displayName(project: CatalogProject): string {
  return isComingSoon(project) ? "朝花夕拾" : project.name;
}

function displayDescription(project: CatalogProject): string {
  if (isComingSoon(project)) return "星露谷风格的田园生活，正在开发中。";
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
  if (newCoverSlugs.has(project.slug)) {
    return staticAssetUrl(`${newCatalogAssetPath}/covers/${project.slug}.webp`);
  }
  return staticAssetUrl(`${catalogAssetPath}/covers/${originalCoverSlugs.has(project.slug) ? project.slug : "discover"}.webp`);
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

// 没有外部作者主页时，展示本站已收录的该作者作品作为简要介绍。
function openAuthorIntro(name: string): void {
  selectedAuthor.value = name;
  void nextTick(() => authorDialog.value?.showModal());
}

function closeAuthorIntro(): void {
  authorDialog.value?.close();
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
            <label class="catalog-search__label" for="catalog-query">搜索项目名称</label>
            <input id="catalog-query" v-model="searchInput" type="search" placeholder="搜索项目名称..." autocomplete="off" @search="submitSearch" />
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
              <button v-for="category in categories" :key="category.id" type="button" class="catalog-filter" :class="[`catalog-filter--${category.slug}`, { 'is-active': selectedCategory === category.slug }]" :aria-pressed="selectedCategory === category.slug" @click="selectedCategory = category.slug">
                <img v-if="category.iconUrl" :src="category.iconUrl" alt="" width="22" height="22" />
                <AimOutlined v-else-if="category.slug === 'shooting'" aria-hidden="true" />
                <ThunderboltOutlined v-else-if="category.slug === 'racing'" aria-hidden="true" />
                <SmileOutlined v-else-if="category.slug === 'funny'" aria-hidden="true" />
                <BulbOutlined v-else-if="category.slug === 'puzzle'" aria-hidden="true" />
                <CoffeeOutlined v-else-if="category.slug === 'casual'" aria-hidden="true" />
                <AppstoreOutlined v-else aria-hidden="true" />
                {{ category.name }}
              </button>
              <button v-if="hasComingSoon" type="button" class="catalog-filter catalog-filter--coming-soon" :class="{ 'is-active': selectedCategory === COMING_SOON_FILTER }" :aria-pressed="selectedCategory === COMING_SOON_FILTER" @click="selectedCategory = COMING_SOON_FILTER">
                <HourglassOutlined aria-hidden="true" /> 敬请期待
              </button>
            </div>
            <div v-if="selectedCategory !== COMING_SOON_FILTER" class="catalog-sort" role="group" aria-label="项目排序">
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
            <article v-for="(project, index) in displayedProjects" :key="project.id" class="catalog-card" :class="{ 'catalog-card--coming-soon': isComingSoon(project) }">
              <div class="catalog-card__media">
                <!-- 站内项目保持路由跳转，外链当前页直达原站；首屏三张封面优先加载。 -->
                <RouterLink v-if="project.kind === 'internal'" class="catalog-card__media-link" :to="project.url" :aria-label="`打开${displayName(project)}`">
                  <img :src="coverUrl(project)" alt="" :loading="index < 3 ? 'eager' : 'lazy'" decoding="async" />
                </RouterLink>
                <a v-else class="catalog-card__media-link" :href="project.url" :aria-label="isComingSoon(project) ? `查看${displayName(project)}的开发进度` : `打开${displayName(project)}`">
                  <img :src="coverUrl(project)" alt="" :loading="index < 3 ? 'eager' : 'lazy'" decoding="async" />
                </a>
                <div class="catalog-card__badges">
                  <span v-if="isNew(project)" class="catalog-card__badge catalog-card__badge--new" role="img" aria-label="新项目" title="新项目"><ClockCircleFilled aria-hidden="true" /></span>
                  <span v-if="isHot(project) && !isComingSoon(project)" class="catalog-card__badge catalog-card__badge--hot" role="img" aria-label="热门项目" title="热门项目"><FireFilled aria-hidden="true" /></span>
                </div>
              </div>
              <div class="catalog-card__body">
                <h2>
                  <RouterLink v-if="project.kind === 'internal'" class="catalog-card__title-link" :to="project.url">{{ displayName(project) }}</RouterLink>
                  <a v-else class="catalog-card__title-link" :href="project.url">{{ displayName(project) }}</a>
                </h2>
                <p class="catalog-card__description">{{ displayDescription(project) }}</p>
                <p class="catalog-card__author">
                  作者：<span v-if="isOriginalProject(project)">原创</span>
                  <a v-else-if="project.authorName && project.authorUrl" :href="project.authorUrl" :aria-label="`查看${project.authorName}的作者链接`">{{ project.authorName }}</a>
                  <button v-else-if="project.authorName" type="button" :aria-label="`查看${project.authorName}的作品`" @click="openAuthorIntro(project.authorName)">{{ project.authorName }}</button>
                  <span v-else>待补充</span>
                </p>
                <div v-if="isComingSoon(project)" class="catalog-card__footer catalog-card__footer--coming-soon">
                  <span>持续开发中</span>
                  <a class="catalog-card__open" :href="project.url" :aria-label="`查看${displayName(project)}的开发进度`"><ArrowRightOutlined aria-hidden="true" /></a>
                </div>
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
                  <a v-else class="catalog-card__open" :href="project.url" :aria-label="`打开${displayName(project)}`"><ArrowRightOutlined aria-hidden="true" /></a>
                </div>
                <p v-if="ratingErrorProjectId === project.id" class="catalog-card__rating-error" role="alert">评分暂时不可用，请稍后重试。</p>
              </div>
            </article>
          </div>
          <div v-if="displayedProjects.length < visibleProjects.length" class="catalog-load-more">
            <button type="button" @click="loadMoreProjects">加载更多</button>
            <span>还有 {{ visibleProjects.length - displayedProjects.length }} 个项目</span>
          </div>
          <!-- 预告项目没有评分入口，评分说明只跟随已开放项目列表。 -->
          <p v-if="selectedCategory !== COMING_SOON_FILTER && visibleProjects.length > 0" class="catalog-list__rating-note">每个项目每位访客只能评一次，提交后不可修改。</p>
        </template>
      </section>
      <footer class="catalog-footer">平行线 · 发现有趣的项目</footer>
    </div>
    <dialog ref="authorDialog" class="catalog-author-dialog" aria-labelledby="catalog-author-dialog-title" @close="selectedAuthor = null">
      <h2 id="catalog-author-dialog-title">{{ selectedAuthor }}</h2>
      <p>本站已收录的作品</p>
      <ul>
        <li v-for="project in selectedAuthorProjects" :key="project.id">
          <RouterLink v-if="project.kind === 'internal'" :to="project.url" @click="closeAuthorIntro">{{ displayName(project) }}</RouterLink>
          <a v-else :href="project.url">{{ displayName(project) }}</a>
        </li>
      </ul>
      <button type="button" @click="closeAuthorIntro">关闭</button>
    </dialog>
  </main>
</template>

<style scoped lang="scss" src="./CatalogHomePage.scss"></style>
