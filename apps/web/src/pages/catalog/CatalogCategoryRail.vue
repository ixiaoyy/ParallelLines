<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, onUpdated, ref, watch } from "vue";
import { useQueryClient } from "@tanstack/vue-query";
import { LeftOutlined, RightOutlined } from "@ant-design/icons-vue";
import { useCatalogCategoryPages } from "@/features/catalog/queries";
import { CATALOG_PRIORITY_SLUGS } from "@/features/catalog/catalogOrder";
import type { CatalogBrowseProject } from "@/features/catalog/model";
import { queryKeys } from "@/shared/api/queryKeys";
import { catalogRailRequestLimit, catalogRailTailTarget, stableCatalogRailPrefix, type CatalogRailGeometry } from "./catalogRailLoading";
import type { CatalogCategoryComposition } from "./catalogCategoryThemes";

const props = defineProps<{
  name: string; slug: string; total: number; composition?: CatalogCategoryComposition;
  coverAspect: (project: CatalogBrowseProject) => number | undefined;
}>();
const root = ref<HTMLElement | null>(null);
const viewport = ref<HTMLElement | null>(null);
const probes = ref<HTMLElement | null>(null);
const canPrevious = ref(false);
const canNext = ref(false);
const near = ref(false);
const started = ref(false);
const localError = ref("");
const requestedLimit = ref(1);
const projects = ref<CatalogBrowseProject[]>([]);
const query = useCatalogCategoryPages(() => props.slug, CATALOG_PRIORITY_SLUGS, requestedLimit);
const queryClient = useQueryClient();
const allItems = computed(() => [...new Map((query.data.value?.pages.flatMap((page) => page.projects) ?? []).map((project) => [project.id, project])).values()]);
const ended = computed(() => props.total === 0 || Boolean(query.data.value?.pages.length && !query.data.value.pages.at(-1)!.hasMore));
const total = computed(() => query.data.value?.pages.at(-1)?.total ?? props.total);
const state = computed(() => !started.value ? "waiting" : localError.value ? "error"
  : query.isFetching.value ? projects.value.length ? "loading-more" : "loading" : ended.value ? "end" : "ready");
let geometry: CatalogRailGeometry | undefined;
let resizeObserver: ResizeObserver | undefined;
let visibilityObserver: IntersectionObserver | undefined;
let frame = 0;
let disposed = false;
let targetRight = 0;
let activePump: Promise<void> | undefined;

/** 只提交新完整三元组，查询统计更新不改变已展示卡片的次序。 */
function commitProjects(): void {
  projects.value = stableCatalogRailPrefix(allItems.value, projects.value.map((project) => project.id), ended.value,
    props.composition, props.coverAspect, (project) => project.viewCount + project.ratingScoreSum * 5);
}
watch(query.data, () => { if (started.value) commitProjects(); });

/** 以真实卡片最右边界计算剩余空间，不能把条数或 scrollWidth 的状态元素当内容宽度。 */
function contentRight(): number {
  const rail = viewport.value;
  const cards = rail?.querySelectorAll<HTMLElement>(".catalog-card");
  const last = cards?.length ? cards[cards.length - 1] : undefined;
  return rail && last ? last.getBoundingClientRect().right - rail.getBoundingClientRect().left + rail.scrollLeft : 0;
}

/** 一个覆盖目标最多四次请求；同分类串行，追加错误保留已有内容和服务端游标。 */
function ensureCoverage(right: number, refresh = false): Promise<void> {
  targetRight = Math.max(targetRight, right);
  if (activePump) return activePump;
  if (!geometry || !started.value || disposed || localError.value) return Promise.resolve();
  activePump = (async () => {
    let requests = 0;
    try {
      // 已发请求可以完成并入缓存；纵向离开附近后，不再补发后续小批。
      while (!disposed && near.value && geometry && requests < 4) {
        const needsInitial = !query.data.value || refresh;
        if (!needsInitial && (ended.value || contentRight() >= targetRight - 1)) break;
        const remaining = needsInitial ? Math.max(props.total, total.value) : Math.max(0, total.value - allItems.value.length);
        requestedLimit.value = catalogRailRequestLimit(geometry, targetRight - contentRight(),
          allItems.value.length - projects.value.length, remaining, props.composition, !allItems.value.length);
        if (!requestedLimit.value) break;
        const before = allItems.value.length;
        const result = needsInitial ? await query.refetch({ cancelRefetch: false }) : await query.fetchNextPage({ cancelRefetch: false });
        requests += 1;
        refresh = false;
        if (disposed) return;
        if (result.error) throw result.error;
        commitProjects();
        await nextTick();
        if (!needsInitial && allItems.value.length <= before && !ended.value) throw new Error("分类分页没有新增项目，请重试。");
      }
      if (!disposed && near.value && requests >= 4 && !ended.value && contentRight() < targetRight - 1) {
        throw new Error("本批加载未完成，请重试继续。");
      }
    } catch (error) {
      if (!disposed) localError.value = error instanceof Error ? error.message : "分类加载失败，请重试。";
    }
  })().finally(() => {
    // 即使命中缓存、无需 await，也在 Promise 赋值后释放互斥状态。
    activePump = undefined;
    if (!disposed) scheduleMeasure();
  });
  return activePump;
}

/** CSS 探针求解 min/calc/cqw 后的像素，列数、lead、竖版和全景宽度均沿实际布局。 */
function measure(): void {
  const rail = viewport.value;
  const sizes = probes.value?.children;
  if (!rail || !sizes?.length || disposed) return;
  const width = rail.clientWidth;
  const oldWidth = geometry?.viewport;
  const size = (index: number) => (sizes[index] as HTMLElement).getBoundingClientRect().width;
  geometry = { viewport: width, gap: Number.parseFloat(getComputedStyle(rail).columnGap) || 0,
    peek: Number.parseFloat(getComputedStyle(root.value!).getPropertyValue("--category-rail-peek")) || 0,
    normal: size(0), lead: size(1), portrait: size(2), panorama: size(3) };
  canPrevious.value = rail.scrollLeft > 2;
  canNext.value = contentRight() - width - rail.scrollLeft > 2 || (started.value && !ended.value && projects.value.length > 0);
  // 屏宽变化后重新建立当前像素目标，不能用宽屏旧目标要求缩窄后的卡片继续补页。
  if (started.value && oldWidth !== undefined && oldWidth !== width) targetRight = rail.scrollLeft + width + geometry.peek;
  if (!(width > 0) || !near.value) return;
  if (!started.value) {
    started.value = true;
    commitProjects();
    const cached = queryClient.getQueryState(queryKeys.catalogCategory(props.slug, CATALOG_PRIORITY_SLUGS.join(",")));
    const stale = Boolean(cached?.isInvalidated || (cached?.dataUpdatedAt && Date.now() - cached.dataUpdatedAt >= 60_000));
    // 缓存前缀先进入 DOM 再量边界，不能因首帧几何尚未更新而误取下一页。
    void nextTick(() => { if (!disposed) void ensureCoverage(width + (geometry?.peek ?? 0), stale); });
  } else if (!localError.value && !activePump) {
    // IO 重入可能晚于滚动事件；以当前尾端恢复需求，不能只等待下一次用户滚动。
    const tailTarget = catalogRailTailTarget(geometry, rail.scrollLeft, contentRight());
    if (tailTarget !== null) targetRight = Math.max(targetRight, tailTarget);
    if (contentRight() < targetRight - 1 && !ended.value) void ensureCoverage(targetRight);
  }
}
/** 合并重复布局通知到下一绘制帧，不直接发起网络请求。 */
function scheduleMeasure(): void {
  if (!frame && !disposed) frame = requestAnimationFrame(() => { frame = 0; measure(); });
}

/** 用户横移接近已加载末尾才追加；渲染/图片 load 本身不不断扩大预取目标。 */
function handleScroll(): void {
  measure();
  const rail = viewport.value;
  if (!rail || !geometry || !near.value || localError.value || ended.value) return;
  const tailTarget = catalogRailTailTarget(geometry, rail.scrollLeft, contentRight());
  if (tailTarget !== null) void ensureCoverage(tailTarget);
}
/** 按正负方向滚动约一屏；向后先补足目标区域，返回时不保证网络成功。 */
async function move(direction: number): Promise<void> {
  const rail = viewport.value;
  if (!rail || !geometry) return;
  const left = Math.max(0, rail.scrollLeft + direction * rail.clientWidth * .85);
  if (direction > 0) await ensureCoverage(left + rail.clientWidth + geometry.peek);
  if (disposed) return;
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  rail.scrollTo({ left, behavior: reduced ? "instant" : "smooth" });
}
/** 用户明确重试当前失败游标，保留已加载项和原覆盖目标。 */
function retry(): void {
  localError.value = "";
  void ensureCoverage(targetRight || (geometry?.viewport ?? 0));
}
/** 只处理横排自身焦点下的左右键，不拦截卡片链接或全局游戏按键。 */
function handleKey(event: KeyboardEvent): void {
  if (event.target !== event.currentTarget || !["ArrowLeft", "ArrowRight"].includes(event.key)) return;
  event.preventDefault();
  void move(event.key === "ArrowRight" ? 1 : -1);
}
/** 用当前视口高度的一半作纵向预取距离；重建时释放旧观察器。 */
function observeVisibility(): void {
  visibilityObserver?.disconnect();
  visibilityObserver = new IntersectionObserver(([entry]) => {
    near.value = Boolean(entry?.isIntersecting);
    if (near.value) scheduleMeasure();
  }, { rootMargin: `${Math.ceil(window.innerHeight * .5)}px 0px` });
  if (root.value) visibilityObserver.observe(root.value);
}
onMounted(() => {
  resizeObserver = new ResizeObserver(scheduleMeasure);
  if (viewport.value) resizeObserver.observe(viewport.value);
  if (probes.value) resizeObserver.observe(probes.value);
  observeVisibility();
  window.addEventListener("resize", observeVisibility);
  scheduleMeasure();
});
onUpdated(scheduleMeasure);
onUnmounted(() => {
  disposed = true;
  resizeObserver?.disconnect(); visibilityObserver?.disconnect();
  window.removeEventListener("resize", observeVisibility);
  cancelAnimationFrame(frame);
  void queryClient.cancelQueries({ queryKey: queryKeys.catalogCategory(props.slug, CATALOG_PRIORITY_SLUGS.join(",")), exact: true });
});
</script>

<template>
  <div ref="root" class="catalog-category-rail" :data-category-rail="slug" :data-load-state="state" :data-composition="composition" :class="{ 'catalog-category-rail--single': total === 1, 'catalog-category-rail--waiting': !projects.length }">
    <div ref="probes" class="catalog-category-rail__probes" aria-hidden="true"><i /><i /><i /><i /></div>
    <div ref="viewport" class="catalog-category-rail__viewport" :aria-label="`${name}游戏`" :aria-busy="query.isFetching.value" role="group" tabindex="0" @scroll.passive="handleScroll" @keydown="handleKey">
      <slot :projects="projects" />
    </div>
    <div v-if="state === 'loading' || state === 'loading-more'" class="catalog-category-rail__status" role="status">正在加载{{ name }}游戏…</div>
    <div v-if="localError" class="catalog-category-rail__status" role="alert"><span>{{ localError }}</span><button type="button" :aria-label="`重新加载${name}游戏`" @click="retry">重试</button></div>
    <button v-if="canPrevious" class="catalog-category-rail__arrow catalog-category-rail__arrow--previous" type="button" :aria-label="`上一组${name}游戏`" @click="move(-1)"><LeftOutlined aria-hidden="true" /></button>
    <button v-if="canNext" class="catalog-category-rail__arrow catalog-category-rail__arrow--next" type="button" :aria-label="`下一组${name}游戏`" @click="move(1)"><RightOutlined aria-hidden="true" /></button>
  </div>
</template>

<style scoped lang="scss">
.catalog-category-rail {
  --category-columns: 2;
  --category-rail-gap: 4px;
  --category-rail-peek: 20px;
  --category-tile-width: min(220px, calc((100cqw - var(--category-rail-peek) - var(--category-rail-gap) * var(--category-columns)) / var(--category-columns)));
  --category-tile-height: calc(var(--category-tile-width) * 4 / 7);
  --category-lead-width: min(300px, calc(var(--category-tile-width) * var(--category-lead-scale, 1)));
  --category-portrait-width: calc(var(--category-tile-height) * .85);
  --category-panorama-width: min(100cqw, var(--category-single-max-width, 340px), calc(var(--category-tile-width) * 1.6));
  position: relative;
  min-width: 0;
  container-type: inline-size;
}
// 1000/1200 are measured CrazyGames transitions. The other thresholds are
// ParallelLines adaptations, checked against our own container and sidebar.
@media (min-width: 600px) { .catalog-category-rail { --category-columns: 3; } }
@media (min-width: 800px) { .catalog-category-rail { --category-columns: 4; } }
@media (min-width: 1000px) { .catalog-category-rail { --category-columns: 5; } }
@media (min-width: 1200px) { .catalog-category-rail { --category-columns: 6; } }
@media (min-width: 1400px) { .catalog-category-rail { --category-columns: 7; } }
@media (min-width: 1600px) { .catalog-category-rail { --category-columns: 8; } }
@media (min-width: 1800px) { .catalog-category-rail { --category-columns: 9; } }
.catalog-category-rail__viewport {
  display: flex; align-items: flex-end; gap: var(--category-rail-gap);
  overflow-x: auto; overscroll-behavior-inline: contain; scrollbar-width: none;
  scroll-snap-type: x mandatory; scroll-padding-inline: 1px;
  border-radius: var(--catalog-card-radius, 22px);
}
.catalog-category-rail__viewport::-webkit-scrollbar { display: none; }
.catalog-category-rail--waiting .catalog-category-rail__viewport { min-height: var(--category-tile-height); }
.catalog-category-rail__probes { position: absolute; inset: 0 auto auto 0; width: 100%; height: 0; overflow: hidden; visibility: hidden; pointer-events: none; }
.catalog-category-rail__probes > i { display: block; height: 1px; width: var(--category-tile-width); }
.catalog-category-rail__probes > i:nth-child(2) { width: var(--category-lead-width); }
.catalog-category-rail__probes > i:nth-child(3) { width: var(--category-portrait-width); }
.catalog-category-rail__probes > i:nth-child(4) { width: var(--category-panorama-width); }
.catalog-category-rail__status { display: flex; align-items: center; gap: 12px; min-height: 36px; padding-top: 8px; color: var(--catalog-muted); font-size: 13px; }
.catalog-category-rail__status button { min-height: 36px; border: 0; border-radius: 6px; padding: 0 12px; color: var(--catalog-ink); background: #dce6da; cursor: pointer; }
.catalog-category-rail[data-composition="mixed"] .catalog-category-rail__viewport { overflow-anchor: none; scroll-snap-type: none; }
.catalog-category-rail__viewport > :deep(.catalog-card) {
  width: var(--category-tile-width);
  min-width: 0; height: var(--category-tile-height); flex: 0 0 auto;
  aspect-ratio: auto; scroll-snap-align: start;
}
.catalog-category-rail[data-composition="mixed"] :deep(.catalog-card[data-cover-format="portrait"] .catalog-card__cover img),
.catalog-category-rail[data-composition="panorama"] :deep(.catalog-card__cover img) { object-fit: contain; }
.catalog-category-rail[data-composition="panorama"] .catalog-category-rail__viewport > :deep(.catalog-card) {
  width: var(--category-panorama-width);
  height: auto;
  aspect-ratio: 7 / 4;
}
@media (min-width: 761px) {
  // One modest lead, not a repeated percentage-based page filling pattern.
  .catalog-category-rail:not([data-composition="balanced"]):not([data-composition="panorama"]) .catalog-category-rail__viewport > :deep(.catalog-card:first-child:not([data-cover-format="portrait"])) {
    width: var(--category-lead-width);
    height: calc(var(--category-tile-height) * var(--category-lead-height-scale, 1));
  }
  // Portrait placement follows the measured source format, never a card index.
  .catalog-category-rail[data-composition="mixed"] .catalog-category-rail__viewport > :deep(.catalog-card[data-cover-format="portrait"]) {
    width: var(--category-portrait-width);
    height: calc(var(--category-tile-height) * 1.35);
  }
}
.catalog-category-rail__arrow {
  position: absolute; z-index: 4; top: 50%; display: grid; width: 44px; height: 44px;
  place-items: center; transform: translateY(-50%); border: 1px solid #ffffff9c;
  border-radius: 50%; color: #fff; background: #505a54ce; font-size: 22px; cursor: pointer;
}
.catalog-category-rail__arrow:hover { background: #315f4e; }
.catalog-category-rail__arrow--next { right: -9px; }
.catalog-category-rail__arrow--previous { left: -9px; }
@media (max-width: 760px) {
  .catalog-category-rail { --category-lead-width: var(--category-tile-width); --category-portrait-width: max(44px, calc(var(--category-tile-height) * 17 / 27)); }
  .catalog-category-rail__viewport > :deep(.catalog-card) { height: auto; aspect-ratio: auto; }
  .catalog-category-rail :deep(.catalog-card__cover) { aspect-ratio: 7 / 4; }
  .catalog-category-rail[data-composition="mixed"] .catalog-category-rail__viewport > :deep(.catalog-card[data-cover-format="portrait"]) { width: var(--category-portrait-width); }
  .catalog-category-rail[data-composition="mixed"] :deep(.catalog-card[data-cover-format="portrait"] .catalog-card__cover) { aspect-ratio: 17 / 27; }
  .catalog-category-rail[data-composition="panorama"] .catalog-category-rail__viewport > :deep(.catalog-card) { aspect-ratio: auto; }
  .catalog-category-rail__arrow { width: 44px; height: 44px; font-size: 18px; }
  .catalog-category-rail__arrow--next { right: -7px; }
  .catalog-category-rail__arrow--previous { left: -7px; }
}
</style>
