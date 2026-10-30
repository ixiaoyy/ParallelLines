<script setup lang="ts">
import { CloseOutlined, CrownFilled, HeartFilled, RightOutlined, UserOutlined, SearchOutlined, SendOutlined, StarOutlined } from "@ant-design/icons-vue";
import { computed, defineAsyncComponent, ref, watch } from "vue";

import { useCurrentUser } from "@/features/auth/queries";

import type { CatalogProject } from "@/features/catalog/model";
import { catalogAuthorKey, rankCatalogAuthors } from "@/features/catalog/authorRanking";
import { categoryVisualFor } from "@/features/catalog/categoryVisuals";
import { getCatalogCoverPath } from "@/features/catalog/coverManifest";
import { useCatalog, useRecordCatalogProjectView } from "@/features/catalog/queries";
import { readPersonalLibrary, recordRecentProject, savePersonalLibrary, toggleWantedProject } from "@/features/catalog/personalLibrary";
import type { PersonalLibrary } from "@/features/catalog/personalLibrary";
import { staticAssetUrl } from "@/shared/assets/staticAssets";
import { useMediaQuery } from "@/shared/lib/useMediaQuery";
import SiteNavigation from "@/shared/ui/SiteNavigation.vue";
import CatalogSiteNavigation from "./CatalogSiteNavigation.vue";
import CatalogNavigation from "./CatalogNavigation.vue";
import { useCatalogNavigation } from "./catalogNavigation";
import type { CatalogFeed } from "./catalogNavigation";

import CatalogSubmissionDialog from "./CatalogSubmissionDialog.vue";
import CatalogLeaderboard from "./CatalogLeaderboard.vue";
import CatalogCategoryOrnament from "./CatalogCategoryOrnament.vue";
import CatalogGameCard from "./CatalogGameCard.vue";
import CatalogAiRating from "./CatalogAiRating.vue";
import CatalogIcon from "./CatalogIcon.vue";
import CatalogSectionTail from "./CatalogSectionTail.vue";
import { categorySectionStyleFor } from "./catalogCategoryThemes";
import CatalogBrandMark from "./CatalogBrandMark.vue";
import { CATALOG_HERO_TABS, selectCatalogRecommendations } from "./catalogTopics";

type SortMode = "latest" | "hot";
type CatalogView = "games" | "authors" | "contributors";
type LibraryScope = "all" | "wanted" | "recent";
type CatalogEntry = CatalogProject & { categorySlug: string; heat: number };
const PAGE_SIZE = 24;
const AUTHOR_PAGE_SIZE = 20;
const HEART_HEAT_WEIGHT = 5;
const SOURCE_CONTRIBUTOR_URL = "https://github.com/MartinDelophy/awesome-gpt-6-astra";
const catalogAssetPath = "/catalog/2026-09-24-v1";
const newCatalogAssetPath = "/catalog/2026-09-25-v1";
const originalCoverSlugs = new Set([
  "clock-out", "merge-watermelon", "qin-imperial-factory", "super-mario",
  "csgo-desert", "infinite-garden", "fruit-ninja", "qq-racing",
  "cf-transport", "pelican-bike", "generals-soldiers",
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
const currentUserQuery = useCurrentUser();
const NotificationBell = defineAsyncComponent(() => import("@/features/notifications/components/NotificationBell.vue"));
const viewMutation = useRecordCatalogProjectView();
const searchInput = ref("");
const search = ref("");
const submissionOpen = ref(false);
const catalogView = ref<CatalogView>("games");
const selectedCategory = ref("all");
const sortMode = ref<SortMode>("latest");
const catalogFeed = ref<CatalogFeed>("discovery");
const visibleLimit = ref(PAGE_SIZE);
const authorSearch = ref("");
const authorVisibleLimit = ref(AUTHOR_PAGE_SIZE);
const contributorVisibleLimit = ref(AUTHOR_PAGE_SIZE);
const selectedAuthorKey = ref<string | null>(null);
const catalogSearchInput = ref<HTMLInputElement | null>(null);
const authorDialog = ref<HTMLDialogElement | null>(null);
const selectedAuthor = ref<string | null>(null);
const sixPreviewColumns = useMediaQuery("(min-width: 1850px)");
const fivePreviewColumns = useMediaQuery("(min-width: 1100px)");
const fourPreviewColumns = useMediaQuery("(min-width: 1001px)");
const threePreviewColumns = useMediaQuery("(min-width: 761px)");
const categoryPreviewLimit = computed(() => sixPreviewColumns.value ? 6 : fivePreviewColumns.value ? 5
  : fourPreviewColumns.value ? 4 : threePreviewColumns.value ? 3 : 2);
// 个人清单仅属于当前浏览器；存储异常后本页继续使用内存状态，不覆盖原记录。
const initialLibrary = readPersonalLibrary();
const personalLibrary = ref(initialLibrary.library);
const libraryCanPersist = ref(initialLibrary.canPersist);
const libraryScope = ref<LibraryScope>("all");
const wantedLimitReached = ref(false);
const catalogNavigation = useCatalogNavigation({ catalogView, libraryScope, selectedCategory, selectedAuthorKey,
  sortMode, feed: catalogFeed, search, searchInput });
const heroTopic = catalogNavigation.heroTopic;
const catalogTitle = computed(() => {
  if (catalogView.value !== "games") return catalogView.value === "authors" ? "作者榜" : "贡献榜";
  if (libraryScope.value === "wanted") return "想玩清单";
  if (libraryScope.value === "recent") return "最近打开";
  if (selectedAuthorKey.value === "original") return "站内游戏";
  if (selectedAuthorKey.value) return "作者作品";
  if (selectedCategory.value !== "all") return categoryName(selectedCategory.value);
  if (search.value.trim()) return "搜索结果";
  if (catalogFeed.value === "latest") return "最新游戏";
  if (catalogFeed.value === "hot") return "热门游戏";
  return "从经典游戏到短时乐趣，看看这些值得一试的游戏";
});
const wantedIds = computed(() => new Set(personalLibrary.value.wantedIds));
const recentOrder = computed(() => new Map(personalLibrary.value.recent.map((entry, index) => [entry.projectId, index])));

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
      // 旧缓存缺失浏览量按零处理；每次浏览计 1 热度，每颗评分心心计 5 热度。
      viewCount: project.viewCount ?? 0,
      heat: (project.viewCount ?? 0) + (project.ratingScoreSum ?? 0) * HEART_HEAT_WEIGHT,
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
// 榜单装饰仅使用该作者真实游戏封面，不把作品图作为作者头像。
const authorCovers = computed(() => {
  const covers = new Map<string, string>();
  for (const project of allProjects.value) {
    const key = catalogAuthorKey(project);
    const cover = coverUrl(project);
    if (key && cover && !covers.has(key)) covers.set(key, cover);
  }
  return covers;
});
const authorLeaderboardEntries = computed(() => displayedAuthors.value.map((author) => ({
  ...author,
  authorKey: author.key,
  cover: authorCovers.value.get(author.key),
  metric: allAuthorHeartsEmpty.value ? `${author.projectCount} 个作品` : `${author.totalHearts} 心`,
  isHeartMetric: !allAuthorHeartsEmpty.value,
  detail: allAuthorHeartsEmpty.value ? undefined : `${author.projectCount} 个作品`,
})));
// 来源贡献固定为第一名，保留开源身份；不为它推算作者作品数。
const contributorLeaderboardEntries = computed(() => [
  {
    key: "source:martindelophy",
    name: "martindelophy",
    rank: 1,
    url: SOURCE_CONTRIBUTOR_URL,
    metric: "开源贡献",
    sourceUrl: SOURCE_CONTRIBUTOR_URL,
  },
  ...displayedContributors.value.map((author) => ({
    ...author,
    authorKey: author.key,
    cover: authorCovers.value.get(author.key),
    metric: `${author.projectCount} 个作品`,
  })),
]);
const selectedAuthorName = computed(() =>
  authorRanks.value.find((author) => author.key === selectedAuthorKey.value)?.name ?? "",
);
const selectedAuthorProjects = computed(() =>
  allProjects.value.filter((project) => project.authorName === selectedAuthor.value),
);
const normalizedSearch = computed(() => search.value.trim().toLocaleLowerCase());
// 个人记录只匹配当前公开目录；暂缺或下架项目不展示，也不因此删除本地记录。
const libraryProjects = computed(() => allProjects.value.filter((project) =>
  libraryScope.value === "wanted" ? wantedIds.value.has(project.id)
    : libraryScope.value === "recent" ? recentOrder.value.has(project.id) : true,
));
// 只有无其他筛选的空个人范围使用清单提示，组合筛选无结果仍沿用原提示。
const emptyLibraryText = computed(() => {
  if (normalizedSearch.value || selectedCategory.value !== "all" || selectedAuthorKey.value) return "没有找到匹配的游戏";
  if (libraryScope.value === "wanted" && personalLibrary.value.wantedIds.length === 0) return "还没有加入想玩的游戏";
  if (libraryScope.value === "recent" && personalLibrary.value.recent.length === 0) return "还没有打开过游戏";
  return "没有找到匹配的游戏";
});

// 分类与排序只改变展示，查询词仅匹配卡片展示名称；开发预览也归入正常分类。
const visibleProjects = computed(() => {
  const matching = libraryProjects.value.filter((project) => {
    if (selectedAuthorKey.value && catalogAuthorKey(project) !== selectedAuthorKey.value) return false;
    if (selectedCategory.value !== "all" && project.categorySlug !== selectedCategory.value) return false;
    if (!normalizedSearch.value) return true;
    return displayName(project).toLocaleLowerCase().includes(normalizedSearch.value);
  });
  return matching.sort((left, right) => {
    // 使用已按时间整理的记录顺序；同一毫秒打开也保留新记录在前，不参与公共排序。
    if (libraryScope.value === "recent") return (recentOrder.value.get(left.id) ?? 0) - (recentOrder.value.get(right.id) ?? 0);
    // 热门按浏览与心心的综合热度排序；相同值仍使用原有最新及稳定顺序。
    if (sortMode.value === "hot") {
      const heat = right.heat - left.heat;
      if (heat) return heat;
    }
    const created = Date.parse(right.createdAt) - Date.parse(left.createdAt);
    if (created) return created;
    const seeded = (seedOrder.get(left.slug) ?? Number.MAX_SAFE_INTEGER)
      - (seedOrder.get(right.slug) ?? Number.MAX_SAFE_INTEGER);
    if (seeded) return seeded;
    // 同秒迁移入库的新游戏按记录 ID 倒序；十进制字符串先比位数，避免大整数转 Number 丢失精度。
    return right.id.length - left.id.length || (left.id < right.id ? 1 : left.id > right.id ? -1 : 0);
  });
});

// 大目录只先渲染首批卡片；筛选变化后重新从首批展示，搜索仍覆盖全部项目。
const displayedProjects = computed(() => visibleProjects.value.slice(0, visibleLimit.value));
const heroProjects = computed(() => selectCatalogRecommendations(allProjects.value, heroTopic.value).slice(0, 6));
// Empty, noninteractive cells preserve the six-slot mosaic without inventing games.
const heroSlots = computed(() => Array.from({ length: 6 }, (_, index) => heroProjects.value[index] ?? null));
// 首页直接复用 API 已按分类聚合的完整公开记录；每类独立取一行，不使用全站分页切片。
const isDiscovery = computed(() => catalogFeed.value === "discovery" && libraryScope.value === "all"
  && selectedCategory.value === "all" && !normalizedSearch.value && !selectedAuthorKey.value);
const presentationGroups = computed(() => {
  if (!isDiscovery.value) return [{ key: "results", name: "", featured: false, visual: undefined,
    total: visibleProjects.value.length, projects: displayedProjects.value }];
  const byCategory = new Map<string, CatalogEntry[]>();
  for (const project of visibleProjects.value) {
    const projects = byCategory.get(project.categorySlug) ?? [];
    projects.push(project);
    byCategory.set(project.categorySlug, projects);
  }
  return [
    { key: "featured", name: "精选推荐", featured: true, visual: undefined,
      total: heroProjects.value.length, projects: heroProjects.value },
    ...categories.value.map((category) => {
      const projects = byCategory.get(category.slug) ?? [];
      return { key: category.slug, name: category.name, featured: false, visual: categoryVisualFor(category),
        total: projects.length, projects: projects.slice(0, categoryPreviewLimit.value) };
    }).filter((group) => group.projects.length),
  ];
});

/** 为同一真实游戏在不同推荐/分类组中的卡片生成稳定展示键，不产生业务写入。 */
function projectCardKey(groupKey: string, projectId: string): string {
  return `${groupKey}:${projectId}`;
}

/** 分类组头复用实际分类筛选，进入每批 24 条的完整分类列表。 */
function browseCategory(slug: string): void {
  catalogNavigation.category(slug);
}

function clearCatalogFilters(): void {
  search.value = "";
  searchInput.value = "";
  selectedCategory.value = "all";
  selectedAuthorKey.value = null;
}

watch([normalizedSearch, selectedCategory, sortMode, selectedAuthorKey, libraryScope], () => {
  visibleLimit.value = PAGE_SIZE;
});
watch(normalizedAuthorSearch, () => { authorVisibleLimit.value = AUTHOR_PAGE_SIZE; });

function loadMoreProjects(): void {
  visibleLimit.value += PAGE_SIZE;
}

/** 切换全部或个人清单范围；scope 沿用现有范围值，不改收藏和最近记录。 */
function selectLibraryScope(scope: LibraryScope): void {
  libraryScope.value = scope;
  // 站内作为独立快捷入口；切换范围时退出站内，其他作者的组合筛选仍保留。
  if (selectedAuthorKey.value === "original") selectedAuthorKey.value = null;
}

function showAuthorGames(key: string): void {
  catalogNavigation.author(key);
}

function clearAuthorGames(): void {
  selectedAuthorKey.value = null;
}

// 按原游戏标识识别我的星露谷。
function isPreviewProject(project: CatalogProject): boolean {
  return project.slug === "fablespace";
}

// 站内游戏与我的星露谷统一展示站内标签，不用网址或后台空值推断具体作者。
function isSiteHostedProject(project: CatalogProject): boolean {
  return project.kind === "internal" || project.slug === "fablespace";
}

function displayName(project: CatalogProject): string {
  return isPreviewProject(project) ? "我的星露谷" : project.name;
}

function categoryName(slug: string): string {
  return allCategories.value.find((category) => category.slug === slug)?.name ?? "游戏";
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

function submitSearch(): void {
  search.value = searchInput.value;
  catalogView.value = "games";
}

function closeAuthorIntro(): void {
  authorDialog.value?.close();
}

/** 更新个人清单的页面状态并尝试保存；失败后保留内存操作，同时显示持久化限制。 */
function updatePersonalLibrary(library: PersonalLibrary): void {
  personalLibrary.value = library;
  if (libraryCanPersist.value) libraryCanPersist.value = savePersonalLibrary(library);
}

/** 切换指定游戏的想玩状态；达到容量时不改现有清单，不触发评分或打开请求。 */
function toggleWanted(project: CatalogProject): void {
  const updated = toggleWantedProject(personalLibrary.value, project.id);
  wantedLimitReached.value = updated === null;
  if (updated) updatePersonalLibrary(updated);
}

// 游戏链接由浏览器直接打开新标签；仅左键/键盘点击和中键各记录一次，右键菜单不计数。
// 参数为目标游戏与链接事件；不拦截默认行为、不移动目录或关闭作者弹窗。
function recordGameOpen(project: CatalogProject, event: MouseEvent): void {
  if (event.type === "click" ? event.button !== 0 : event.type !== "auxclick" || event.button !== 1) return;
  // 只记有效点击，不推断实际游玩；本地保存与原累计量请求互不依赖。
  updatePersonalLibrary(recordRecentProject(personalLibrary.value, project.id));
  viewMutation.mutate({ projectId: project.id });
}

</script>

<!--
THESIS: 以真实游戏封面构成可浏览的游乐场，第一屏同时看到多款游戏。
OWN-WORLD: 温灰纸面、玉青导航、深墨绿文字；少量民俗书卷装饰；目录局部动作与焦点采用墨绿、玉青。
STORY: 看推荐，按真实分类探索，搜索或收藏，然后原生打开游戏。
FIRST VIEWPORT: 窄图标侧栏、紧凑顶栏与搜索；双大图夹四小图推荐，下接分类封面组。
FORM: 用户选定 Library 玉青＋温灰参考；推荐和分类来自当前 API，无固定游戏列表。
-->
<template>
  <main class="catalog-page" :class="`catalog-page--${catalogView}`" aria-labelledby="catalog-title">
    <header class="catalog-header">
      <div class="catalog-header__inner">
        <RouterLink class="catalog-brand" :to="{ name: 'home' }" aria-label="平行线首页"><CatalogBrandMark /><span>平行线</span></RouterLink>
        <CatalogSiteNavigation />
        <form class="catalog-search" role="search" @submit.prevent="submitSearch"><SearchOutlined aria-hidden="true" /><label class="catalog-search__label" for="catalog-query">搜索游戏名称</label><input id="catalog-query" ref="catalogSearchInput" v-model="searchInput" type="search" placeholder="搜索游戏名称..." autocomplete="off" @search="submitSearch" /><button type="submit">搜索</button></form>
        <button type="button" class="catalog-header__submit" aria-label="投稿游戏" @click="submissionOpen = true"><SendOutlined aria-hidden="true" /><span>投稿游戏</span></button>
        <div class="catalog-header__actions">
          <NotificationBell v-if="currentUserQuery.data.value" />
          <button type="button" class="catalog-icon-button" aria-label="想玩清单" title="想玩清单" @click="catalogNavigation.navigate('wanted')"><StarOutlined aria-hidden="true" /></button>
          <RouterLink class="catalog-account" :to="currentUserQuery.data.value ? { name: 'account-home' } : { name: 'auth', query: { redirect: '/games' } }" :aria-label="currentUserQuery.data.value ? '个人中心' : '登录/注册'" :title="currentUserQuery.data.value?.display_name || currentUserQuery.data.value?.username || '登录/注册'"><UserOutlined aria-hidden="true" /></RouterLink>
        </div>
      </div>
    </header>
    <CatalogNavigation :active="catalogNavigation.active.value" :categories="categories" :selected-category="selectedCategory"
      @navigate="catalogNavigation.navigate" @category="browseCategory" />
    <div class="catalog-page__wrap">
      <section class="catalog-intro" :class="{ 'catalog-intro--discovery': isDiscovery }">
        <h1 v-if="isDiscovery" id="catalog-title">从经典游戏到<span>短时乐趣</span>，看看这些值得一试的游戏</h1>
        <h1 v-else id="catalog-title">{{ catalogTitle }}</h1>
        <img v-if="isDiscovery" class="catalog-intro__landscape" :src="staticAssetUrl('/catalog/2026-10-29-ui/bridge-spring.png')" alt="" width="258" height="96" decoding="async" aria-hidden="true" />
        <nav v-if="isDiscovery" class="catalog-recommendation-tabs" aria-label="发现游戏">
          <button v-for="tab in CATALOG_HERO_TABS" :key="tab.id" type="button" :class="{ 'is-active': heroTopic === tab.id }" :aria-pressed="heroTopic === tab.id" @click="catalogNavigation.topic(tab.id)">{{ tab.name }}</button>
        </nav>
      </section>
      <section class="catalog-list" aria-label="游戏与作者">
        <div v-if="catalogQuery.isLoading.value" class="catalog-state catalog-state--loading" role="status" aria-label="正在加载游戏目录"><span class="catalog-state__spinner" aria-hidden="true"></span><span>正在加载游戏目录…</span></div>
        <div v-else-if="catalogQuery.isError.value" class="catalog-state" role="alert"><span>项目目录暂时不可用，请稍后重试。</span><button type="button" @click="catalogQuery.refetch()">重新加载</button></div>
        <template v-else>
          <template v-if="catalogView === 'games'">
            <div v-if="!isDiscovery" class="catalog-controls">
              <div class="catalog-library-filters" role="group" aria-label="游戏范围">
                <button type="button" :class="{ 'is-active': libraryScope === 'all' && selectedAuthorKey !== 'original' }" :aria-pressed="libraryScope === 'all' && selectedAuthorKey !== 'original'" @click="selectLibraryScope('all')"><CatalogIcon name="game" /><span>全部游戏</span></button>
                <button type="button" :class="{ 'is-active': selectedAuthorKey === 'original' }" :aria-pressed="selectedAuthorKey === 'original'" @click="showAuthorGames('original')"><CrownFilled aria-hidden="true" /><span>站内</span></button>
                <button type="button" class="catalog-library-filter--wanted" :class="{ 'is-active': libraryScope === 'wanted' }" :aria-pressed="libraryScope === 'wanted'" @click="selectLibraryScope('wanted')"><HeartFilled aria-hidden="true" /><span>想玩清单</span></button>
                <button type="button" :class="{ 'is-active': libraryScope === 'recent' }" :aria-pressed="libraryScope === 'recent'" @click="selectLibraryScope('recent')"><CatalogIcon name="recent" /><span>最近打开</span></button>
              </div>
              <span class="catalog-results" role="status">{{ visibleProjects.length }} 个游戏</span>
              <div class="catalog-categories"><label for="catalog-category">分类：</label><select id="catalog-category" v-model="selectedCategory" aria-label="游戏分类"><option value="all">全部</option><option v-for="category in categories" :key="category.id" :value="category.slug">{{ category.name }}</option></select></div>
              <div v-if="libraryScope !== 'recent'" class="catalog-sort">
                <label for="catalog-sort">排序：</label><select id="catalog-sort" v-model="sortMode" aria-label="游戏排序"><option value="latest">最新</option><option value="hot">热门</option></select>
              </div>
            </div>

            <p v-if="!libraryCanPersist" class="catalog-library__notice" role="alert">本地存储不可用，当前清单只在本次页面访问期间保留。</p>
            <p v-if="wantedLimitReached" class="catalog-library__notice" role="alert">想玩清单最多保存 500 款游戏，请先移出部分游戏。</p>
            <div v-if="selectedAuthorKey && selectedAuthorKey !== 'original'" class="catalog-author-selection"><span>正在查看 <strong>{{ selectedAuthorName || '该作者' }}</strong> 的作品</span><button type="button" @click="clearAuthorGames">清除作者筛选</button></div>
            <div v-if="visibleProjects.length === 0" class="catalog-state" role="status"><span>{{ emptyLibraryText }}</span><button v-if="search || selectedCategory !== 'all' || selectedAuthorKey" type="button" @click="clearCatalogFilters">清除筛选</button></div>
            <div v-else class="catalog-groups">
              <section v-for="group in presentationGroups" :key="group.key" class="catalog-group" :class="{ 'catalog-group--featured': group.featured, 'catalog-group--illustrated': group.visual?.artwork, 'catalog-group--themed': !group.featured && group.name }" :style="group.visual ? { ...categorySectionStyleFor(group.key), '--category-art-wash': group.visual.wash, '--category-art-ink': group.visual.ink } : undefined" :aria-label="group.name || '游戏列表'">
                <CatalogSectionTail v-if="group.visual" :slug="group.key" />
                <header v-if="group.name && !group.featured" class="catalog-group__heading">
                  <div class="catalog-group__title"><CatalogCategoryOrnament v-if="group.visual?.artwork" :visual="group.visual" /><h2><button type="button" @click="browseCategory(group.key)">{{ group.name }}<RightOutlined aria-hidden="true" /></button></h2></div>
                  <div class="catalog-group__meta"><span class="catalog-group__count">共 {{ group.total }} 款 · 展示 {{ group.projects.length }} 款</span><button type="button" :aria-label="`查看全部${group.name}游戏`" @click="browseCategory(group.key)">查看更多 <RightOutlined aria-hidden="true" /></button></div>
                </header>
                <div class="catalog-grid" :class="{ 'catalog-grid--featured': group.featured }">
                  <template v-for="(project, index) in group.featured ? heroSlots : group.projects" :key="project?.id ?? `empty:${index}`">
                    <CatalogGameCard v-if="project"
                      :title="displayName(project)" :href="project.url" :cover="coverUrl(project)" :category-name="categoryName(project.categorySlug)"
                      :author-name="project.authorName" :site-hosted="isSiteHostedProject(project)"
                      :heat="project.heat" :wanted="wantedIds.has(project.id)" :eager="index < 3"
                      :featured="group.featured && (index === 0 || index === 5)" :data-hero-slot="group.featured ? index : undefined"
                      :data-project-id="project.id" :data-card-key="projectCardKey(group.key, project.id)"
                      @open="recordGameOpen(project, $event)" @toggle-wanted="toggleWanted(project)">
                      <template #rating><CatalogAiRating :rating="project.aiRating" :game-name="displayName(project)" /></template>
                    </CatalogGameCard>
                    <span v-else class="catalog-hero-slot-empty" :class="{ 'catalog-hero-slot-empty--featured': index === 0 || index === 5 }" :data-hero-slot="index" aria-hidden="true"></span>
                  </template>
                  <p v-if="group.featured && heroProjects.length === 0" class="catalog-hero-empty" role="status">暂无符合该推荐主题的游戏</p>
                </div>
              </section>
            </div>
            <div v-if="!isDiscovery && displayedProjects.length < visibleProjects.length" class="catalog-load-more"><button type="button" @click="loadMoreProjects">加载更多</button><span>还有 {{ visibleProjects.length - displayedProjects.length }} 个游戏</span></div>
          </template>
          <CatalogLeaderboard v-else-if="catalogView === 'authors'" variant="authors" title="作者榜" :entries="authorLeaderboardEntries" :has-more="displayedAuthors.length < matchingAuthors.length" more-label="加载更多作者" @show-games="showAuthorGames" @load-more="authorVisibleLimit += AUTHOR_PAGE_SIZE">
            <template #tools><span class="catalog-author-count" role="status">{{ matchingAuthors.length }} 位作者</span><label class="catalog-author-search" for="catalog-author-query"><span class="catalog-icon catalog-icon--search" aria-hidden="true"></span><span class="catalog-search__label">搜索作者</span><input id="catalog-author-query" v-model="authorSearch" type="search" placeholder="搜索作者名称..." autocomplete="off" /></label></template>
          </CatalogLeaderboard>
          <CatalogLeaderboard v-else variant="contributors" title="贡献榜" :entries="contributorLeaderboardEntries" :has-more="displayedContributors.length < rankedContributors.length" more-label="加载更多贡献者" @show-games="showAuthorGames" @load-more="contributorVisibleLimit += AUTHOR_PAGE_SIZE" />

        </template>
      </section>
      <footer class="catalog-footer"><div><strong>平行线</strong><span>让好玩的小游戏被更多人发现</span></div><SiteNavigation /><p class="catalog-library__hint">记录保存在当前浏览器，清理浏览器数据后会丢失。</p></footer>
    </div>
    <CatalogSubmissionDialog v-model:open="submissionOpen" />
    <dialog ref="authorDialog" class="catalog-author-dialog" aria-labelledby="catalog-author-dialog-title" @close="selectedAuthor = null">
      <div class="catalog-author-dialog__header"><div><h2 id="catalog-author-dialog-title">{{ selectedAuthor }}</h2><span>{{ selectedAuthorProjects.length }} 个游戏</span></div><button type="button" class="catalog-author-dialog__close" aria-label="关闭作者窗口" @click="closeAuthorIntro"><CloseOutlined aria-hidden="true" /></button></div>
      <ul class="catalog-author-dialog__games"><li v-for="project in selectedAuthorProjects" :key="project.id"><a :href="project.url" target="_blank" rel="noopener noreferrer" @click="recordGameOpen(project, $event)" @auxclick="recordGameOpen(project, $event)"><img v-if="coverUrl(project)" :src="coverUrl(project) ?? undefined" alt="" loading="lazy" /><span>{{ displayName(project) }}</span><span class="catalog-icon catalog-icon--arrow" aria-hidden="true"></span></a></li></ul>
    </dialog>
  </main>
</template>

<style scoped lang="scss" src="./CatalogHomePage.scss"></style>
<style scoped lang="scss" src="./CatalogCategorySection.scss"></style>
