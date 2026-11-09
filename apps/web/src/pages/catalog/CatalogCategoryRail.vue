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
const widthProbe = ref<HTMLElement | null>(null);
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
        const filled = contentRight();
        if (!needsInitial && (ended.value || filled >= targetRight - 1)) break;
        const remaining = needsInitial ? Math.max(props.total, total.value) : Math.max(0, total.value - allItems.value.length);
        // 卡片不再等宽：用已呈现的实际平均宽度估算缺口，已覆盖的边界仍以 DOM 为准。
        const count = projects.value.length;
        const observedWidth = count > 0 ? (filled - (count - 1) * geometry.gap) / count : undefined;
        requestedLimit.value = catalogRailRequestLimit(geometry, targetRight - filled,
          allItems.value.length - count, remaining, props.composition, observedWidth);
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

/** 测量轨道和首批估算宽度；有真实卡后，补页以已渲染几何为准。 */
function measure(): void {
  const rail = viewport.value;
  const probe = widthProbe.value;
  if (!rail || !probe || disposed) return;
  const width = rail.clientWidth;
  const oldWidth = geometry?.viewport;
  geometry = { viewport: width, gap: Number.parseFloat(getComputedStyle(rail).columnGap) || 0,
    peek: Number.parseFloat(getComputedStyle(root.value!).getPropertyValue("--category-rail-peek")) || 0,
    estimatedWidth: probe.getBoundingClientRect().width };
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
  if (widthProbe.value) resizeObserver.observe(widthProbe.value);
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
  <div ref="root" class="catalog-category-rail" :data-category-rail="slug" :data-load-state="state" :data-composition="composition" :class="{ 'catalog-category-rail--single': total === 1 }">
    <div ref="widthProbe" class="catalog-category-rail__width-probe" aria-hidden="true"></div>
    <div ref="viewport" class="catalog-category-rail__viewport" :aria-label="`${name}游戏`" :aria-busy="query.isFetching.value" role="group" tabindex="0" @scroll.passive="handleScroll" @keydown="handleKey">
      <slot :projects="projects" />
    </div>
    <div v-if="state === 'loading' || state === 'loading-more'" class="catalog-category-rail__status" role="status">正在加载{{ name }}游戏…</div>
    <div v-if="localError" class="catalog-category-rail__status catalog-category-rail__status--error" role="alert"><span>{{ localError }}</span><button type="button" :aria-label="`重新加载${name}游戏`" @click="retry">重试</button></div>
    <button v-if="canPrevious" class="catalog-category-rail__arrow catalog-category-rail__arrow--previous" type="button" :aria-label="`上一组${name}游戏`" @click="move(-1)"><LeftOutlined aria-hidden="true" /></button>
    <button v-if="canNext" class="catalog-category-rail__arrow catalog-category-rail__arrow--next" type="button" :aria-label="`下一组${name}游戏`" @click="move(1)"><RightOutlined aria-hidden="true" /></button>
  </div>
</template>

<style scoped lang="scss">
.catalog-category-rail {
  --category-rail-gap: 4px;
  --category-rail-peek: 20px;
  --category-tile-height: clamp(76px, calc(66px + 3.2cqw), 114px);
  --category-max-cover-width: min(100cqw, 340px);
  // 只在比例未知或估算首批时借用常见正式封面 960×452 的比例。
  --category-estimated-aspect: 2.1239;
  position: relative;
  min-width: 0;
  container-type: inline-size;
}
.catalog-category-rail__viewport {
  display: flex; align-items: flex-end; gap: var(--category-rail-gap);
  // 初载、图片解码和补页共用同一行高，状态浮层不再撑开下方分类。
  height: var(--category-tile-height);
  overflow-x: auto; overscroll-behavior-inline: contain; scrollbar-width: none;
  scroll-snap-type: x mandatory; scroll-padding-inline: 1px;
  border-radius: var(--catalog-card-radius, 22px);
}
.catalog-category-rail__viewport::-webkit-scrollbar { display: none; }
.catalog-category-rail__width-probe {
  position: absolute; inset: 0 auto auto 0; height: 0; visibility: hidden; pointer-events: none;
  width: min(var(--category-max-cover-width), calc(var(--category-tile-height) * var(--category-estimated-aspect)));
}
.catalog-category-rail__status { position: absolute; z-index: 3; left: 8px; bottom: calc(var(--category-caption-height, 0px) + 8px); display: flex; max-width: calc(100% - 16px); max-height: calc(100% - var(--category-caption-height, 0px) - 16px); align-items: center; gap: 8px; overflow: auto; border-radius: 8px; padding: 6px 10px; color: var(--catalog-muted); background: var(--category-section-bg, var(--catalog-paper)); font-size: 13px; pointer-events: none; }
// 错误仍可阅读并定向重试；加载提示透传点击，不挡住已有游戏或横向浏览。
.catalog-category-rail__status--error { z-index: 5; align-items: flex-start; pointer-events: auto; }
.catalog-category-rail__status span { min-width: 0; overflow-wrap: anywhere; }
.catalog-category-rail__status button { min-width: 44px; min-height: 44px; flex-shrink: 0; border: 0; border-radius: 6px; padding: 0 12px; color: var(--catalog-ink); background: #dce6da; cursor: pointer; }
.catalog-category-rail[data-composition="mixed"] .catalog-category-rail__viewport { overflow-anchor: none; scroll-snap-type: none; }
.catalog-category-rail__viewport > :deep(.catalog-card) {
  // 同排按基准高度换算宽度；超宽卡碰到上限后整张等比缩小，不从边缘切掉内容。
  --category-card-aspect: var(--category-cover-aspect, var(--category-estimated-aspect));
  width: min(var(--category-max-cover-width), calc(var(--category-tile-height) * var(--category-card-aspect)));
  flex: none;
  aspect-ratio: var(--category-card-aspect);
  scroll-snap-align: start;
}
.catalog-category-rail__viewport > :deep(.catalog-card .catalog-card__cover img) { object-fit: contain; }
.catalog-category-rail__arrow {
  position: absolute; z-index: 4; top: 50%; display: grid; width: 44px; height: 44px;
  place-items: center; transform: translateY(-50%); border: 1px solid #ffffff9c;
  border-radius: 50%; color: #fff; background: #505a54ce; font-size: 22px; cursor: pointer;
}
.catalog-category-rail__arrow:hover { background: #315f4e; }
.catalog-category-rail__arrow--next { right: -9px; }
.catalog-category-rail__arrow--previous { left: -9px; }
@media (max-width: 760px) {
  // 手机预留固定标题带；原图比例只控制封面，窄竖封和晚到图片不改变行高。
  .catalog-category-rail { --category-caption-height: 32px; }
  .catalog-category-rail__viewport { height: calc(var(--category-tile-height) + var(--category-caption-height)); }
  .catalog-category-rail__viewport > :deep(.catalog-card) { aspect-ratio: auto; }
  .catalog-category-rail__viewport > :deep(.catalog-card .catalog-card__cover) { aspect-ratio: var(--category-card-aspect); }
  .catalog-category-rail__viewport > :deep(.catalog-card .catalog-card__mobile-name) { box-sizing: border-box; height: var(--category-caption-height); }
  .catalog-category-rail__viewport > :deep(.catalog-card .catalog-card__details) { bottom: var(--category-caption-height); max-height: calc(100% - var(--category-caption-height)); }
  .catalog-category-rail__arrow { width: 44px; height: 44px; font-size: 18px; }
  .catalog-category-rail__arrow--next { right: -7px; }
  .catalog-category-rail__arrow--previous { left: -7px; }
}
</style>
