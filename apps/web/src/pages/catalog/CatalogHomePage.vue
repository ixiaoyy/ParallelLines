<script setup lang="ts">
import {
  AimOutlined, AppstoreOutlined, ArrowRightOutlined, BulbOutlined,
  ClockCircleFilled, CoffeeOutlined, FireFilled, HeartFilled,
  HeartOutlined, SearchOutlined, SmileOutlined, StarFilled, ThunderboltOutlined, TrophyOutlined, UploadOutlined,
} from "@ant-design/icons-vue";
import { computed, nextTick, ref, watch } from "vue";

import type { CatalogProject } from "@/features/catalog/model";
import { catalogAuthorKey, rankCatalogAuthors } from "@/features/catalog/authorRanking";
import { getCatalogCoverPath } from "@/features/catalog/coverManifest";
import { useCatalog, useRateCatalogProject } from "@/features/catalog/queries";
import { cssUrl, staticAssetUrl } from "@/shared/assets/staticAssets";

import CatalogSubmissionDialog from "./CatalogSubmissionDialog.vue";

type SortMode = "latest" | "hot";
type CatalogView = "games" | "authors" | "contributors";
type CatalogEntry = CatalogProject & { categorySlug: string };
const PAGE_SIZE = 24;
const AUTHOR_PAGE_SIZE = 20;
const SOURCE_CONTRIBUTOR_URL = "https://github.com/MartinDelophy/awesome-gpt-6-astra";
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
const submissionOpen = ref(false);
const catalogView = ref<CatalogView>("games");
const selectedCategory = ref("all");
const sortMode = ref<SortMode>("latest");
const visibleLimit = ref(PAGE_SIZE);
const authorSearch = ref("");
const authorVisibleLimit = ref(AUTHOR_PAGE_SIZE);
const contributorVisibleLimit = ref(AUTHOR_PAGE_SIZE);
const selectedAuthorKey = ref<string | null>(null);
const pendingProjectId = ref<string | null>(null);
const ratingErrorProjectId = ref<string | null>(null);
const hoveredProjectId = ref<string | null>(null);
const hoveredScore = ref(0);
const authorDialog = ref<HTMLDialogElement | null>(null);
const selectedAuthor = ref<string | null>(null);

// 种田分类固定在末尾；其余分类仍沿用后台排序。
const allCategories = computed(() => catalogQuery.data.value ?? []);
const categories = computed(() => allCategories.value
  .filter((category) => category.projects.length > 0)
  .sort((left, right) => Number(left.slug === "farming") - Number(right.slug === "farming")));
const allProjects = computed<CatalogEntry[]>(() =>
  allCategories.value.flatMap((category) =>
    category.projects.map((project) => ({
      ...project,
      categorySlug: category.slug,
    })),
  ),
);
// 榜单统计全部公开项目，不能只使用首页首批渲染的卡片。
const authorRanks = computed(() => rankCatalogAuthors(allProjects.value));
const rankedAuthors = computed(() => authorRanks.value.map((author, index) => ({ ...author, rank: index + 1 })));
const normalizedAuthorSearch = computed(() => authorSearch.value.normalize("NFKC").trim().toLocaleLowerCase());
const matchingAuthors = computed(() => rankedAuthors.value.filter((author) =>
  author.searchText.includes(normalizedAuthorSearch.value),
));
const displayedAuthors = computed(() => matchingAuthors.value.slice(0, authorVisibleLimit.value));
const allAuthorHeartsEmpty = computed(() => authorRanks.value.every((author) => author.totalHearts === 0));
const rankedContributors = computed(() => [...authorRanks.value]
  .filter((author) => author.name.toLocaleLowerCase() !== "martindelophy")
  .sort((left, right) => right.projectCount - left.projectCount
    || right.totalHearts - left.totalHearts
    || left.name.localeCompare(right.name, "zh-CN"))
  .map((author, index) => ({ ...author, rank: index + 2 })));
const displayedContributors = computed(() => rankedContributors.value.slice(0, contributorVisibleLimit.value));
const selectedAuthorName = computed(() =>
  authorRanks.value.find((author) => author.key === selectedAuthorKey.value)?.name ?? "",
);
const selectedAuthorProjects = computed(() =>
  allProjects.value.filter((project) => project.authorName === selectedAuthor.value),
);
const normalizedSearch = computed(() => search.value.trim().toLocaleLowerCase());

// 分类与排序只改变展示，查询词仅匹配卡片展示名称；开发预览也归入正常分类。
const visibleProjects = computed(() => {
  const matching = allProjects.value.filter((project) => {
    if (selectedAuthorKey.value && catalogAuthorKey(project) !== selectedAuthorKey.value) return false;
    if (selectedCategory.value !== "all" && project.categorySlug !== selectedCategory.value) return false;
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
watch([normalizedSearch, selectedCategory, sortMode, selectedAuthorKey], () => {
  visibleLimit.value = PAGE_SIZE;
});
watch(normalizedAuthorSearch, () => { authorVisibleLimit.value = AUTHOR_PAGE_SIZE; });

function loadMoreProjects(): void {
  visibleLimit.value += PAGE_SIZE;
}

function showAuthorGames(key: string): void {
  selectedAuthorKey.value = key;
  selectedCategory.value = "all";
  search.value = "";
  searchInput.value = "";
  catalogView.value = "games";
}

function clearAuthorGames(): void {
  selectedAuthorKey.value = null;
}

// 朝花夕拾仍是开发预览，可进入游戏页面，但暂不接受评分。
function isPreviewProject(project: CatalogProject): boolean {
  return project.slug === "fablespace";
}

// 站内游戏与朝花夕拾统一展示原创署名，不用网址或后台空值推断具体作者。
function isOriginalProject(project: CatalogProject): boolean {
  return project.kind === "internal" || project.slug === "fablespace";
}

function displayName(project: CatalogProject): string {
  return isPreviewProject(project) ? "朝花夕拾" : project.name;
}

function displayDescription(project: CatalogProject): string {
  if (isPreviewProject(project)) return "星露谷风格的田园生活，正在开发中。";
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

// 后台封面优先；首批专属图和后续原创卡面均使用各自的版本化 CDN 地址。
function coverUrl(project: CatalogProject): string | null {
  if (project.iconUrl) return project.iconUrl;
  if (newCoverSlugs.has(project.slug)) {
    return staticAssetUrl(`${newCatalogAssetPath}/covers/${project.slug}.webp`);
  }
  if (originalCoverSlugs.has(project.slug)) {
    return staticAssetUrl(`${catalogAssetPath}/covers/${project.slug}.webp`);
  }
  const importedCover = getCatalogCoverPath(project.slug);
  return importedCover ? staticAssetUrl(importedCover) : null;
}

// 新审核项目尚无专属图时，以项目自己的名称和分类绘制卡面，避免重复旧占位图。
function fallbackCoverTone(slug: string): number {
  return [...slug].reduce((sum, char) => sum + char.charCodeAt(0), 0) % 6;
}

function categoryName(slug: string): string {
  return allCategories.value.find((category) => category.slug === slug)?.name ?? "游戏";
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
  catalogView.value = "games";
}

// 没有外部作者主页时，展示本站已收录的该作者作品作为简要介绍。
function openAuthorIntro(name: string): void {
  selectedAuthor.value = name;
  void nextTick(() => authorDialog.value?.showModal());
}

function closeAuthorIntro(): void {
  authorDialog.value?.close();
}

// 游客只提交首次评分；开发预览暂不开放评分。
async function rateProject(project: CatalogProject, score: number): Promise<void> {
  if (isPreviewProject(project) || project.myScore !== null || pendingProjectId.value !== null) return;
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
          <div class="catalog-hero__actions">
            <form class="catalog-search" role="search" @submit.prevent="submitSearch">
              <SearchOutlined class="catalog-search__icon" aria-hidden="true" />
              <label class="catalog-search__label" for="catalog-query">搜索项目名称</label>
              <input id="catalog-query" v-model="searchInput" type="search" placeholder="搜索项目名称..." autocomplete="off" @search="submitSearch" />
              <button type="submit">搜索</button>
            </form>
            <button type="button" class="catalog-hero__submit" @click="submissionOpen = true"><UploadOutlined aria-hidden="true" /> 上传游戏</button>
          </div>
        </div>
        <img class="catalog-hero__mascot" :src="mascotUrl" alt="" width="430" height="430" />
      </div>
    </section>

    <div class="catalog-page__wrap">
      <section class="catalog-list" aria-label="游戏与作者">
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
          <div class="catalog-view-tabs" role="group" aria-label="浏览内容">
            <button type="button" :class="{ 'is-active': catalogView === 'games' }" :aria-pressed="catalogView === 'games'" @click="catalogView = 'games'">游戏目录</button>
            <button type="button" :class="{ 'is-active': catalogView === 'authors' }" :aria-pressed="catalogView === 'authors'" @click="catalogView = 'authors'">作者排行</button>
            <button type="button" :class="{ 'is-active': catalogView === 'contributors' }" :aria-pressed="catalogView === 'contributors'" @click="catalogView = 'contributors'">贡献榜</button>
          </div>
          <template v-if="catalogView === 'games'">
          <div v-if="selectedAuthorKey" class="catalog-author-selection">
            <span>正在查看 <strong>{{ selectedAuthorName || '该作者' }}</strong> 的作品</span>
            <button type="button" @click="clearAuthorGames">清除作者筛选</button>
          </div>
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
                <span v-else-if="category.slug === 'farming'" class="catalog-filter__emoji" aria-hidden="true">🌱</span>
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
            <button v-if="search || selectedCategory !== 'all' || selectedAuthorKey" type="button" @click="search = ''; searchInput = ''; selectedCategory = 'all'; selectedAuthorKey = null">清除筛选</button>
          </div>
          <div v-else class="catalog-grid">
            <article v-for="(project, index) in displayedProjects" :key="project.id" class="catalog-card" :class="{ 'catalog-card--preview': isPreviewProject(project) }">
              <div class="catalog-card__media">
                <!-- 站内项目保持路由跳转，外链当前页直达原站；首屏三张封面优先加载。 -->
                <RouterLink v-if="project.kind === 'internal'" class="catalog-card__media-link" :to="project.url" :aria-label="`打开${displayName(project)}`">
                  <img v-if="coverUrl(project)" :src="coverUrl(project) ?? undefined" alt="" :loading="index < 3 ? 'eager' : 'lazy'" decoding="async" />
                  <span v-else class="catalog-card__cover-fallback" :class="`catalog-card__cover-fallback--${fallbackCoverTone(project.slug)}`" aria-hidden="true"><span>{{ categoryName(project.categorySlug) }}</span><strong>{{ displayName(project) }}</strong><i>✦</i></span>
                </RouterLink>
                <a v-else class="catalog-card__media-link" :href="project.url" :aria-label="isPreviewProject(project) ? `查看${displayName(project)}的开发进度` : `打开${displayName(project)}`">
                  <img v-if="coverUrl(project)" :src="coverUrl(project) ?? undefined" alt="" :loading="index < 3 ? 'eager' : 'lazy'" decoding="async" />
                  <span v-else class="catalog-card__cover-fallback" :class="`catalog-card__cover-fallback--${fallbackCoverTone(project.slug)}`" aria-hidden="true"><span>{{ categoryName(project.categorySlug) }}</span><strong>{{ displayName(project) }}</strong><i>✦</i></span>
                </a>
                <div class="catalog-card__badges">
                  <span v-if="isNew(project)" class="catalog-card__badge catalog-card__badge--new" role="img" aria-label="新项目" title="新项目"><ClockCircleFilled aria-hidden="true" /></span>
                  <span v-if="isHot(project) && !isPreviewProject(project)" class="catalog-card__badge catalog-card__badge--hot" role="img" aria-label="热门项目" title="热门项目"><FireFilled aria-hidden="true" /></span>
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
                <div v-if="isPreviewProject(project)" class="catalog-card__footer catalog-card__footer--preview">
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
          <!-- 开发预览没有评分入口，评分说明只跟随可评分项目列表。 -->
          <p v-if="visibleProjects.some((project) => !isPreviewProject(project))" class="catalog-list__rating-note">每个项目每位访客只能评一次，提交后不可修改。</p>
          </template>
          <section v-else-if="catalogView === 'authors'" class="catalog-leaderboard" aria-labelledby="author-ranking-title">
            <div class="catalog-leaderboard__header">
              <div><h2 id="author-ranking-title"><TrophyOutlined aria-hidden="true" /> 作者排行</h2><p>累计所有作品获得的心心；暂无评分时按作品数排序。</p></div>
              <label class="catalog-author-search" for="catalog-author-query"><SearchOutlined aria-hidden="true" /><span>搜索作者</span><input id="catalog-author-query" v-model="authorSearch" type="search" placeholder="搜索作者名称..." autocomplete="off" /></label>
            </div>
            <p class="catalog-leaderboard__count" role="status">{{ matchingAuthors.length }} 位作者</p>
            <p v-if="!matchingAuthors.length" class="catalog-leaderboard__empty">没有找到匹配的作者。</p>
            <ol v-else class="catalog-leaderboard__list">
              <li v-for="author in displayedAuthors" :key="author.key" class="catalog-leaderboard__row">
                <span class="catalog-leaderboard__rank" :class="{ 'is-first': author.rank === 1 }">{{ author.rank }}</span>
                <div class="catalog-leaderboard__identity"><a v-if="author.url" :href="author.url" target="_blank" rel="noopener noreferrer">{{ author.name }}</a><strong v-else>{{ author.name }}</strong><small v-if="!allAuthorHeartsEmpty">{{ author.projectCount }} 个作品</small></div>
                <span class="catalog-leaderboard__metric"><HeartFilled v-if="!allAuthorHeartsEmpty" aria-hidden="true" /> {{ allAuthorHeartsEmpty ? `${author.projectCount} 个作品` : `${author.totalHearts} 心` }}</span>
                <button type="button" class="catalog-leaderboard__open" :aria-label="`查看${author.name}的作品`" @click="showAuthorGames(author.key)">查看作品 <ArrowRightOutlined aria-hidden="true" /></button>
              </li>
            </ol>
            <button v-if="displayedAuthors.length < matchingAuthors.length" type="button" class="catalog-leaderboard__more" @click="authorVisibleLimit += AUTHOR_PAGE_SIZE">加载更多作者</button>
          </section>
          <section v-else class="catalog-leaderboard" aria-labelledby="contributor-ranking-title">
            <div class="catalog-leaderboard__header"><div><h2 id="contributor-ranking-title"><TrophyOutlined aria-hidden="true" /> 贡献榜</h2><p>感谢开源清单的整理者；其他作者按本站收录的作品数排序。</p></div></div>
            <ol class="catalog-leaderboard__list">
              <li class="catalog-leaderboard__row catalog-leaderboard__row--featured">
                <span class="catalog-leaderboard__rank is-first">1</span>
                <div class="catalog-leaderboard__identity"><a :href="SOURCE_CONTRIBUTOR_URL" target="_blank" rel="noopener noreferrer">martindelophy</a><small>Awesome GPT-6 Astra 开源清单</small></div>
                <span class="catalog-leaderboard__metric">收录线索贡献</span>
                <a class="catalog-leaderboard__open" :href="SOURCE_CONTRIBUTOR_URL" target="_blank" rel="noopener noreferrer">查看开源项目 <ArrowRightOutlined aria-hidden="true" /></a>
              </li>
              <li v-for="author in displayedContributors" :key="author.key" class="catalog-leaderboard__row">
                <span class="catalog-leaderboard__rank">{{ author.rank }}</span>
                <div class="catalog-leaderboard__identity"><a v-if="author.url" :href="author.url" target="_blank" rel="noopener noreferrer">{{ author.name }}</a><strong v-else>{{ author.name }}</strong></div>
                <span class="catalog-leaderboard__metric">{{ author.projectCount }} 个作品</span>
                <button type="button" class="catalog-leaderboard__open" :aria-label="`查看${author.name}的作品`" @click="showAuthorGames(author.key)">查看作品 <ArrowRightOutlined aria-hidden="true" /></button>
              </li>
            </ol>
            <button v-if="displayedContributors.length < rankedContributors.length" type="button" class="catalog-leaderboard__more" @click="contributorVisibleLimit += AUTHOR_PAGE_SIZE">加载更多贡献者</button>
          </section>
        </template>
      </section>
      <footer class="catalog-footer">平行线 · 发现有趣的项目</footer>
    </div>
    <CatalogSubmissionDialog v-model:open="submissionOpen" />
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
