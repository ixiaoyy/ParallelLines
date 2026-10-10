<script setup lang="ts">
import { AppstoreFilled, BarChartOutlined, CaretRightFilled, CloseOutlined, CrownFilled, FireFilled, HeartFilled, MenuOutlined, SearchOutlined, SendOutlined, StarFilled, StarOutlined } from "@ant-design/icons-vue";
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";

import type { CatalogProject } from "@/features/catalog/model";
import { catalogAuthorKey, rankCatalogAuthors } from "@/features/catalog/authorRanking";
import { getCatalogCoverPath } from "@/features/catalog/coverManifest";
import { useCatalog, useRecordCatalogProjectView } from "@/features/catalog/queries";
import { readPersonalLibrary, recordRecentProject, savePersonalLibrary, toggleWantedProject } from "@/features/catalog/personalLibrary";
import type { PersonalLibrary } from "@/features/catalog/personalLibrary";
import { staticAssetUrl } from "@/shared/assets/staticAssets";

import CatalogSubmissionDialog from "./CatalogSubmissionDialog.vue";
import CatalogLeaderboard from "./CatalogLeaderboard.vue";

type SortMode = "latest" | "hot";
type CatalogView = "games" | "authors" | "contributors";
type LibraryScope = "all" | "wanted" | "recent";
type LayoutMode = "grid" | "list";
type CardTone = "red" | "blue" | "yellow" | "green" | "purple" | "teal" | "pink" | "sky";
type CatalogEntry = CatalogProject & { categorySlug: string; heat: number };
// 三个目录视图只切换各自的装饰短句，排名、筛选与数据源保持原状态。
const HERO_MOTTO: Record<CatalogView, readonly string[]> = {
  games: ["PLAY", "EXPLORE", "INDIE", "TOGETHER"],
  authors: ["PLAY", "CREATE", "SHARE", "TOGETHER"],
  contributors: ["PLAY", "SHARE", "CONTRIBUTE", "TOGETHER"],
};
const PAGE_SIZE = 24;
const AUTHOR_PAGE_SIZE = 20;
const HEART_HEAT_WEIGHT = 5;
const SOURCE_CONTRIBUTOR_URL = "https://github.com/MartinDelophy/awesome-gpt-6-astra";
const catalogAssetPath = "/catalog/2026-09-24-v1";
const newCatalogAssetPath = "/catalog/2026-09-25-v1";
const CARD_TONES: CardTone[] = ["red", "blue", "yellow", "green", "purple", "teal", "pink", "sky"];
// 参考图里的八款游戏固定掌机外壳配色；其余游戏仍由真实标识稳定分配。
const FEATURED_CARD_TONES = new Map<string, CardTone>([
  ["soulforge", "red"],
  ["achroma", "blue"],
  ["bubble-tank", "yellow"],
  ["pelican-rider", "green"],
  ["shousui", "purple"],
  ["sketch-rts", "teal"],
  ["snake-escape", "pink"],
  ["flappy-dunk", "sky"],
]);
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
const viewMutation = useRecordCatalogProjectView();
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
// 显示方式只属于本次页面访问，不写入个人清单或公共目录。
const layoutMode = ref<LayoutMode>("grid");
const catalogSearchInput = ref<HTMLInputElement | null>(null);
const authorDialog = ref<HTMLDialogElement | null>(null);
const selectedAuthor = ref<string | null>(null);
// 街机选框仅跟随当前可见游戏，不写入个人清单，也不替代链接与收藏控件的原生焦点。
const catalogPage = ref<HTMLElement | null>(null);
const catalogGrid = ref<HTMLDivElement | null>(null);
const selectedProjectId = ref<string | null>(null);
// 个人清单仅属于当前浏览器；存储异常后本页继续使用内存状态，不覆盖原记录。
const initialLibrary = readPersonalLibrary();
const personalLibrary = ref(initialLibrary.library);
const libraryCanPersist = ref(initialLibrary.canPersist);
const libraryScope = ref<LibraryScope>("all");
const wantedLimitReached = ref(false);
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
// 筛选后优先保留仍可见的选中游戏；原游戏消失时从当前结果的第一项重新选择。
watch(() => displayedProjects.value.map((project) => project.id), (ids) => {
  if (!selectedProjectId.value || !ids.includes(selectedProjectId.value)) {
    selectedProjectId.value = ids[0] ?? null;
  }
}, { immediate: true });
watch([normalizedSearch, selectedCategory, sortMode, selectedAuthorKey, libraryScope], () => {
  visibleLimit.value = PAGE_SIZE;
});
watch(normalizedAuthorSearch, () => { authorVisibleLimit.value = AUTHOR_PAGE_SIZE; });

onMounted(() => window.addEventListener("keydown", handleArcadeKeydown));
onUnmounted(() => window.removeEventListener("keydown", handleArcadeKeydown));

/** 在首页非编辑区域或页面初始焦点下用 WASD 移动选框；Enter 保留当前原生控件的操作。 */
function handleArcadeKeydown(event: KeyboardEvent): void {
  if (event.defaultPrevented || event.isComposing || event.altKey || event.ctrlKey || event.metaKey
    || catalogView.value !== "games" || submissionOpen.value || selectedAuthor.value !== null) return;
  const key = event.key.toLowerCase();
  if (!["w", "a", "s", "d", "enter"].includes(key)) return;
  const grid = catalogGrid.value;
  const target = event.target;
  if (!grid || !(target instanceof Element)) return;
  // 加载更多、筛选及视图按钮保留焦点时仍可移动选框；范围限于本首页，编辑控件与弹层继续独占按键。
  if (target !== document.body && target !== document.documentElement && !catalogPage.value?.contains(target)) return;
  if (target.closest("input, select, textarea, [contenteditable]:not([contenteditable='false']), [role='textbox'], [role='combobox']")
    || document.querySelector("dialog[open], [role='dialog'][aria-modal='true']")) return;
  // 卡片链接和按钮不阻断 WASD；Enter 仍交给当前控件，避免再次打开选中游戏。
  if (key === "enter" && target.closest("a, button, summary, [role='button'], [role='link']")) return;
  const cards = [...grid.querySelectorAll<HTMLElement>(".catalog-card")];
  const index = cards.findIndex((card) => card.dataset.projectId === selectedProjectId.value);
  const current = cards[index];
  if (!current) return;
  event.preventDefault();
  // Enter 在当前真实按键事件内同步点击原链接，保留新标签、最近打开与累计浏览量的既有链路。
  if (key === "enter") {
    if (!event.repeat) current.querySelector<HTMLAnchorElement>(".catalog-card__open")?.click();
    return;
  }
  const columns = getComputedStyle(grid).gridTemplateColumns.trim().split(/\s+/).length;
  const column = index % columns;
  const row = Math.floor(index / columns);
  // 水平移动不跨行，最后一行不足整列时向下落到该行末项；列表模式自然按一列移动。
  const nextIndex = key === "w" && row > 0 ? index - columns
    : key === "s" && row < Math.ceil(cards.length / columns) - 1 ? Math.min(cards.length - 1, index + columns)
      : key === "a" && column > 0 ? index - 1
        : key === "d" && column < columns - 1 ? Math.min(cards.length - 1, index + 1) : index;
  const next = cards[nextIndex];
  if (!next) return;
  selectedProjectId.value = next.dataset.projectId ?? null;
  next.focus({ preventScroll: true });
  next.scrollIntoView({ block: "nearest", inline: "nearest", behavior: "instant" });
}

function loadMoreProjects(): void {
  visibleLimit.value += PAGE_SIZE;
}

function showAuthorGames(key: string): void {
  selectedAuthorKey.value = key;
  selectedCategory.value = "all";
  search.value = "";
  searchInput.value = "";
  catalogView.value = "games";
  // 从公共作者榜进入作品时恢复完整目录，避免此前个人范围隐藏作者作品。
  libraryScope.value = "all";
}

function clearAuthorGames(): void {
  selectedAuthorKey.value = null;
}

// 朝花夕拾仍是开发预览，打开入口继续展示开发进度。
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

/** 根据真实游戏标识返回掌机外壳颜色；指定游戏沿用设计稿，其余标识稳定映射到八色。 */
function cardTone(slug: string): CardTone {
  const featuredTone = FEATURED_CARD_TONES.get(slug);
  if (featuredTone) return featuredTone;
  // 未指定游戏使用固定哈希，不因分类、排序或本次加载顺序变化而换色。
  let hash = 0;
  for (const char of slug) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
  return CARD_TONES[hash % CARD_TONES.length]!;
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

function submitSearch(): void {
  search.value = searchInput.value;
  catalogView.value = "games";
}

/** 从顶部搜索入口返回游戏目录，并在对应输入框挂载后将焦点移到搜索。 */
async function focusCatalogSearch(): Promise<void> {
  catalogView.value = "games";
  await nextTick();
  catalogSearchInput.value?.focus();
}

// 没有外部作者主页时，展示本站已收录的该作者作品作为简要介绍。
function openAuthorIntro(name: string): void {
  selectedAuthor.value = name;
  void nextTick(() => authorDialog.value?.showModal());
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

<template>
  <main ref="catalogPage" class="catalog-page" :class="`catalog-page--${catalogView}`" aria-labelledby="catalog-title">
    <header class="catalog-header">
      <div class="catalog-page__wrap catalog-header__inner">
        <RouterLink class="catalog-brand" to="/" aria-label="平行线首页">
          <img src="/logo-lines-mark.png" alt="" width="92" height="82" />
          <span>平行线</span>
        </RouterLink>
        <span class="catalog-header__tagline">发现更多好玩的小游戏</span>
        <nav class="catalog-view-tabs" aria-label="浏览内容">
          <button type="button" :class="{ 'is-active': catalogView === 'games' }" :aria-pressed="catalogView === 'games'" @click="catalogView = 'games'"><span class="catalog-icon catalog-icon--gamepad" aria-hidden="true"></span><span>游戏目录</span></button>
          <button type="button" :class="{ 'is-active': catalogView === 'authors' }" :aria-pressed="catalogView === 'authors'" @click="catalogView = 'authors'"><CrownFilled aria-hidden="true" /><span>作者榜</span></button>
          <button type="button" :class="{ 'is-active': catalogView === 'contributors' }" :aria-pressed="catalogView === 'contributors'" @click="catalogView = 'contributors'"><BarChartOutlined aria-hidden="true" /><span>贡献榜</span></button>
        </nav>
        <button type="button" class="catalog-header__search" aria-label="搜索游戏" @click="focusCatalogSearch"><SearchOutlined aria-hidden="true" /></button>
        <button type="button" class="catalog-header__submit" @click="submissionOpen = true"><SendOutlined aria-hidden="true" /><span>投稿游戏</span></button>
        <span class="catalog-header__mascot" aria-hidden="true"><img src="/catalog/night-arcade-v1/header-mascot.webp" alt="" width="56" height="56" /></span>
      </div>
    </header>
    <section class="catalog-hero" :class="{ 'catalog-hero--leaderboard': catalogView !== 'games' }" aria-labelledby="catalog-title">
      <div class="catalog-hero__inner">
        <img v-if="catalogView !== 'games'" class="catalog-hero__emblem" :src="catalogView === 'authors' ? '/catalog/night-arcade-v1/gold-crown.webp' : '/catalog/night-arcade-v1/trophy-medal.webp'" alt="" aria-hidden="true" width="64" height="48" />
        <h1 id="catalog-title"><template v-if="catalogView === 'games'">今天想玩<span>点什么</span>？</template><template v-else>{{ catalogView === 'authors' ? '作者榜' : '贡献榜' }}</template></h1>
        <p v-if="catalogView === 'games'" class="catalog-hero__subtitle">在 平行线，发现更多好玩的小游戏！</p>
        <p v-else class="catalog-hero__leaderboard-subtitle">{{ catalogView === 'authors' ? '用小游戏，点亮更多人的快乐' : '每一份贡献，都让这个游乐场更好' }}</p>
        <form v-if="catalogView === 'games'" class="catalog-search" role="search" @submit.prevent="submitSearch">
          <SearchOutlined aria-hidden="true" />
          <label class="catalog-search__label" for="catalog-query">搜索游戏名称</label>
          <input id="catalog-query" ref="catalogSearchInput" v-model="searchInput" type="search" placeholder="搜索游戏名称..." autocomplete="off" @search="submitSearch" />
          <button type="submit">搜索</button>
        </form>
        <p class="catalog-hero__motto" aria-hidden="true"><template v-for="(word, index) in HERO_MOTTO[catalogView]" :key="word"><b v-if="index > 0">+</b><span>{{ word }}</span></template><b>+</b><HeartFilled /></p>
      </div>
    </section>
    <div class="catalog-page__wrap">
      <section class="catalog-list" aria-label="游戏与作者">
        <div v-if="catalogQuery.isLoading.value" class="catalog-state catalog-state--loading" role="status" aria-label="正在加载游戏目录"><span class="catalog-state__spinner" aria-hidden="true"></span><span>正在加载游戏目录…</span></div>
        <div v-else-if="catalogQuery.isError.value" class="catalog-state" role="alert"><span>项目目录暂时不可用，请稍后重试。</span><button type="button" @click="catalogQuery.refetch()">重新加载</button></div>
        <template v-else>
          <template v-if="catalogView === 'games'">
            <!-- 清单、分类和排序各自保留原状态；数量置于工具栏，避免挤占卡片行。 -->
            <div class="catalog-controls">
              <div class="catalog-library-filters" role="group" aria-label="全部游戏、想玩清单、最近打开">
                <button type="button" :class="{ 'is-active': libraryScope === 'all' }" :aria-pressed="libraryScope === 'all'" @click="libraryScope = 'all'"><span class="catalog-icon catalog-icon--gamepad" aria-hidden="true"></span><span>全部游戏</span></button>
                <button type="button" :class="{ 'is-active': libraryScope === 'wanted' }" :aria-pressed="libraryScope === 'wanted'" @click="libraryScope = 'wanted'"><HeartFilled aria-hidden="true" /><span>想玩清单</span></button>
                <button type="button" :class="{ 'is-active': libraryScope === 'recent' }" :aria-pressed="libraryScope === 'recent'" @click="libraryScope = 'recent'"><span class="catalog-icon catalog-icon--clock" aria-hidden="true"></span><span>最近打开</span></button>
              </div>
              <span class="catalog-results" role="status">{{ visibleProjects.length }} 个游戏</span>
              <div class="catalog-categories"><label for="catalog-category">分类：</label><select id="catalog-category" v-model="selectedCategory" aria-label="游戏分类"><option value="all">全部</option><option v-for="category in categories" :key="category.id" :value="category.slug">{{ category.name }}</option></select></div>
              <div v-if="libraryScope !== 'recent'" class="catalog-sort">
                <label for="catalog-sort">排序：</label><select id="catalog-sort" v-model="sortMode" aria-label="游戏排序"><option value="latest">最新</option><option value="hot">热门</option></select>
              </div>
              <div class="catalog-layout-toggle" role="group" aria-label="目录显示方式">
                <button type="button" :class="{ 'is-active': layoutMode === 'grid' }" :aria-pressed="layoutMode === 'grid'" aria-label="网格显示" @click="layoutMode = 'grid'"><AppstoreFilled aria-hidden="true" /></button>
                <button type="button" :class="{ 'is-active': layoutMode === 'list' }" :aria-pressed="layoutMode === 'list'" aria-label="列表显示" @click="layoutMode = 'list'"><MenuOutlined aria-hidden="true" /></button>
              </div>
            </div>
            <p class="catalog-arcade-hint"><kbd>W/A/S/D</kbd> 选择 · <kbd>Enter</kbd> 开始游戏</p>
            <p v-if="!libraryCanPersist" class="catalog-library__notice" role="alert">本地存储不可用，当前清单只在本次页面访问期间保留。</p>
            <p v-if="wantedLimitReached" class="catalog-library__notice" role="alert">想玩清单最多保存 500 款游戏，请先移出部分游戏。</p>
            <div v-if="selectedAuthorKey" class="catalog-author-selection"><span>正在查看 <strong>{{ selectedAuthorName || '该作者' }}</strong> 的作品</span><button type="button" @click="clearAuthorGames">清除作者筛选</button></div>
            <div v-if="visibleProjects.length === 0" class="catalog-state" role="status"><span>{{ emptyLibraryText }}</span><button v-if="search || selectedCategory !== 'all' || selectedAuthorKey" type="button" @click="search = ''; searchInput = ''; selectedCategory = 'all'; selectedAuthorKey = null">清除筛选</button></div>
            <div v-else ref="catalogGrid" class="catalog-grid" :class="{ 'catalog-grid--list': layoutMode === 'list' }">
              <article v-for="(project, index) in displayedProjects" :key="project.id" class="catalog-card" :class="[`catalog-card--${cardTone(project.slug)}`, { 'catalog-card--preview': isPreviewProject(project), 'is-selected': selectedProjectId === project.id }]" :data-project-id="project.id" :aria-current="selectedProjectId === project.id ? 'true' : undefined" tabindex="-1" @pointerdown="selectedProjectId = project.id" @focusin="selectedProjectId = project.id">
                <span v-if="selectedProjectId === project.id" class="catalog-card__selection-frame" aria-hidden="true"></span>
                <!-- 封面延伸到屏幕底部，信息和操作叠在画面内，保留各自独立的原生入口。 -->
                <div class="catalog-card__screen">
                  <div class="catalog-card__media">
                    <a class="catalog-card__media-link" :href="project.url" target="_blank" rel="noopener noreferrer" :aria-label="isPreviewProject(project) ? `查看${displayName(project)}的开发进度` : `打开${displayName(project)}`" @click="recordGameOpen(project, $event)" @auxclick="recordGameOpen(project, $event)">
                      <img v-if="coverUrl(project)" :src="coverUrl(project) ?? undefined" alt="" :loading="index < 3 ? 'eager' : 'lazy'" decoding="async" />
                      <span v-else class="catalog-card__cover-fallback" :class="`catalog-card__cover-fallback--${fallbackCoverTone(project.slug)}`" aria-hidden="true"><span>{{ categoryName(project.categorySlug) }}</span><strong>{{ displayName(project) }}</strong></span>
                    </a>
                    <div class="catalog-card__badges"><span v-if="isNew(project)" class="catalog-card__badge" role="img" aria-label="新游戏" title="新游戏"><span class="catalog-icon catalog-icon--clock" aria-hidden="true"></span></span><span v-if="isHot(project) && !isPreviewProject(project)" class="catalog-card__badge catalog-card__badge--hot" role="img" aria-label="热门游戏" title="热门游戏">HOT</span></div>
                    <!-- 卡片只展示综合热度；累计浏览与历史评分仍沿用原计算和记录链路。 -->
                    <span class="catalog-card__heat" :aria-label="`热度 ${project.heat}`" :title="`热度 ${project.heat}`"><FireFilled aria-hidden="true" />{{ project.heat }}</span>
                  </div>
                  <div class="catalog-card__body">
                    <div class="catalog-card__info">
                      <h2><a class="catalog-card__title-link" :href="project.url" :title="displayName(project)" target="_blank" rel="noopener noreferrer" @click="recordGameOpen(project, $event)" @auxclick="recordGameOpen(project, $event)">{{ displayName(project) }}</a></h2>
                      <p class="catalog-card__author" :title="isOriginalProject(project) ? '原创' : project.authorName || '待补充'"><span v-if="isOriginalProject(project)">原创</span><a v-else-if="project.authorName && project.authorUrl" :href="project.authorUrl" target="_blank" rel="noopener noreferrer" :aria-label="`查看${project.authorName}的作者链接`">{{ project.authorName }}</a><button v-else-if="project.authorName" type="button" :aria-label="`查看${project.authorName}的作品`" @click="openAuthorIntro(project.authorName)">{{ project.authorName }}</button><span v-else>待补充</span></p>
                    </div>
                    <div class="catalog-card__footer">
                      <button type="button" class="catalog-card__wanted" :class="{ 'is-active': wantedIds.has(project.id) }" :aria-pressed="wantedIds.has(project.id)" :aria-label="wantedIds.has(project.id) ? '移出想玩' : '加入想玩'" :title="wantedIds.has(project.id) ? '移出想玩' : '加入想玩'" @click="toggleWanted(project)"><StarFilled v-if="wantedIds.has(project.id)" aria-hidden="true" /><StarOutlined v-else aria-hidden="true" /></button>
                      <a class="catalog-card__open" :href="project.url" target="_blank" rel="noopener noreferrer" :aria-label="isPreviewProject(project) ? `查看${displayName(project)}的开发进度` : `打开${displayName(project)}`" @click="recordGameOpen(project, $event)" @auxclick="recordGameOpen(project, $event)"><CaretRightFilled aria-hidden="true" /><span>{{ isPreviewProject(project) ? '开发进度' : '开始游戏' }}</span></a>
                    </div>
                  </div>
                </div>
              </article>
            </div>
            <div v-if="displayedProjects.length < visibleProjects.length" class="catalog-load-more"><button type="button" @click="loadMoreProjects">加载更多</button><span>还有 {{ visibleProjects.length - displayedProjects.length }} 个游戏</span></div>
          </template>
          <CatalogLeaderboard v-else-if="catalogView === 'authors'" variant="authors" title="作者榜" :entries="authorLeaderboardEntries" :has-more="displayedAuthors.length < matchingAuthors.length" more-label="加载更多作者" @show-games="showAuthorGames" @load-more="authorVisibleLimit += AUTHOR_PAGE_SIZE">
            <template #tools><span class="catalog-author-count" role="status">{{ matchingAuthors.length }} 位作者</span><label class="catalog-author-search" for="catalog-author-query"><span class="catalog-icon catalog-icon--search" aria-hidden="true"></span><span class="catalog-search__label">搜索作者</span><input id="catalog-author-query" v-model="authorSearch" type="search" placeholder="搜索作者名称..." autocomplete="off" /></label></template>
          </CatalogLeaderboard>
          <CatalogLeaderboard v-else variant="contributors" title="贡献榜" :entries="contributorLeaderboardEntries" :has-more="displayedContributors.length < rankedContributors.length" more-label="加载更多贡献者" @show-games="showAuthorGames" @load-more="contributorVisibleLimit += AUTHOR_PAGE_SIZE" />
        </template>
      </section>
    </div>
    <footer class="catalog-footer">
      <div class="catalog-page__wrap catalog-footer__inner">
        <div class="catalog-footer__brand"><strong>平行线</strong><span>让好玩的小游戏被更多人发现</span></div>
        <p class="catalog-footer__motto" aria-hidden="true"><HeartFilled /><span>SMALL GAMES</span><HeartFilled /><span>BIG HAPPINESS</span><HeartFilled /></p>
        <span class="catalog-footer__play" aria-hidden="true"><CaretRightFilled /><CaretRightFilled /><CaretRightFilled /><span>PLAY MORE</span></span>
      </div>
      <p v-if="catalogView === 'games'" class="catalog-library__hint">记录保存在当前浏览器，清理浏览器数据后会丢失。</p>
    </footer>
    <CatalogSubmissionDialog v-model:open="submissionOpen" />
    <dialog ref="authorDialog" class="catalog-author-dialog" aria-labelledby="catalog-author-dialog-title" @close="selectedAuthor = null">
      <div class="catalog-author-dialog__header"><div><h2 id="catalog-author-dialog-title">{{ selectedAuthor }}</h2><span>{{ selectedAuthorProjects.length }} 个游戏</span></div><button type="button" class="catalog-author-dialog__close" aria-label="关闭作者窗口" @click="closeAuthorIntro"><CloseOutlined aria-hidden="true" /></button></div>
      <ul class="catalog-author-dialog__games"><li v-for="project in selectedAuthorProjects" :key="project.id"><a :href="project.url" target="_blank" rel="noopener noreferrer" @click="recordGameOpen(project, $event)" @auxclick="recordGameOpen(project, $event)"><img v-if="coverUrl(project)" :src="coverUrl(project) ?? undefined" alt="" loading="lazy" /><span>{{ displayName(project) }}</span><span class="catalog-icon catalog-icon--arrow" aria-hidden="true"></span></a></li></ul>
    </dialog>
  </main>
</template>

<style scoped lang="scss" src="./CatalogHomePage.scss"></style>
