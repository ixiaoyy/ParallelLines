<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref } from "vue";

import CatalogIcon from "./CatalogIcon.vue";
import type { CatalogIconName } from "./catalogIcons";
import type { CatalogNavId } from "./catalogNavigation";

defineProps<{
  active: string;
  categories: ReadonlyArray<{ id: string; slug: string; name: string }>;
  selectedCategory: string;
}>();

const emit = defineEmits<{
  navigate: [id: CatalogNavId];
  category: [slug: string];
}>();

const items: ReadonlyArray<{ id: CatalogNavId; label: string; icon: CatalogIconName }> = [
  { id: "home", label: "首页", icon: "home" },
  { id: "recent", label: "最近打开", icon: "recent" },
  { id: "latest", label: "最新", icon: "latest" },
  { id: "hot", label: "热门", icon: "hot" },
  { id: "site", label: "站内", icon: "site" },
  { id: "wanted", label: "想玩", icon: "wanted" },
  { id: "authors", label: "作者榜", icon: "authors" },
  { id: "contributors", label: "贡献榜", icon: "contributors" },
];

const navigation = ref<HTMLElement | null>(null);
const categoryTrigger = ref<HTMLButtonElement | null>(null);
const categoryPanel = ref<HTMLElement | null>(null);
const categoryOpen = ref(false);
const tooltip = ref<{ label: string; x: number; y: number; above: boolean } | null>(null);

/** 提示独立于可滚动图标条定位，避免窄屏或短视口把文字裁掉。 */
function showTooltip(event: Event, label: string): void {
  if (!(event.currentTarget instanceof HTMLElement)) return;
  const bounds = event.currentTarget.getBoundingClientRect();
  const above = window.matchMedia("(max-width: 760px)").matches;
  tooltip.value = {
    label,
    x: above ? window.innerWidth / 2 : bounds.right + 10,
    y: above ? bounds.top - 8 : bounds.top + bounds.height / 2,
    above,
  };
}

function hideTooltip(): void {
  tooltip.value = null;
}

function leaveTooltip(event: PointerEvent): void {
  if (event.currentTarget !== document.activeElement) hideTooltip();
}

/** 关闭临时分类面板；Escape 和选择完成时恢复触发按钮焦点。 */
function closeCategories(restoreFocus = false): void {
  if (!categoryOpen.value) return;
  categoryOpen.value = false;
  if (restoreFocus) categoryTrigger.value?.focus();
}

async function openCategories(): Promise<void> {
  if (categoryOpen.value) return;
  hideTooltip();
  categoryOpen.value = true;
  await nextTick();
  const selected = categoryPanel.value?.querySelector<HTMLButtonElement>("button[aria-pressed='true']");
  (selected ?? categoryPanel.value?.querySelector<HTMLButtonElement>(".catalog-navigation__category"))?.focus();
}

async function toggleCategories(): Promise<void> {
  if (categoryOpen.value) {
    closeCategories(true);
    return;
  }
  await openCategories();
}

defineExpose({ openCategories });

function navigate(id: CatalogNavId): void {
  closeCategories();
  hideTooltip();
  emit("navigate", id);
}

function chooseCategory(slug: string): void {
  emit("category", slug);
  closeCategories(true);
}

function handleOutsidePointer(event: PointerEvent): void {
  if (event.target instanceof Node && !navigation.value?.contains(event.target)) closeCategories();
}

function handleResize(): void {
  hideTooltip();
}

onMounted(() => {
  document.addEventListener("pointerdown", handleOutsidePointer, true);
  window.addEventListener("scroll", hideTooltip, { capture: true, passive: true });
  window.addEventListener("resize", handleResize);
});

onUnmounted(() => {
  document.removeEventListener("pointerdown", handleOutsidePointer, true);
  window.removeEventListener("scroll", hideTooltip, true);
  window.removeEventListener("resize", handleResize);
});
</script>

<template>
  <nav ref="navigation" class="catalog-navigation" aria-label="游戏导航" @keydown.esc.stop.prevent="closeCategories(true)">
    <div class="catalog-navigation__items" @scroll.passive="hideTooltip">
      <button
        v-for="item in items"
        :key="item.id"
        type="button"
        class="catalog-navigation__button"
        :class="{ 'is-active': active === item.id, 'is-separated': item.id === 'authors' }"
        :aria-label="item.label"
        :aria-current="active === item.id ? 'page' : undefined"
        @click="navigate(item.id)"
        @pointerenter="showTooltip($event, item.label)"
        @pointerleave="leaveTooltip"
        @focus="showTooltip($event, item.label)"
        @blur="hideTooltip"
      ><CatalogIcon :name="item.icon" /></button>
      <button
        ref="categoryTrigger"
        type="button"
        class="catalog-navigation__button is-separated"
        :class="{ 'is-active': selectedCategory !== 'all' || categoryOpen }"
        aria-label="分类"
        aria-controls="catalog-navigation-categories"
        :aria-expanded="categoryOpen"
        @click="toggleCategories"
        @pointerenter="showTooltip($event, '分类')"
        @pointerleave="leaveTooltip"
        @focus="showTooltip($event, '分类')"
        @blur="hideTooltip"
      ><CatalogIcon name="categories" /></button>
    </div>

    <section v-if="categoryOpen" id="catalog-navigation-categories" ref="categoryPanel" class="catalog-navigation__panel" aria-labelledby="catalog-navigation-categories-title">
      <header class="catalog-navigation__panel-header">
        <h2 id="catalog-navigation-categories-title">游戏分类</h2>
        <button type="button" class="catalog-navigation__close" aria-label="关闭分类" @click="closeCategories(true)"><CatalogIcon name="close" /></button>
      </header>
      <div class="catalog-navigation__categories" role="group" aria-label="选择游戏分类">
        <button type="button" class="catalog-navigation__category" :aria-pressed="selectedCategory === 'all'" @click="chooseCategory('all')">全部分类</button>
        <button v-for="category in categories" :key="category.id" type="button" class="catalog-navigation__category" :aria-pressed="selectedCategory === category.slug" @click="chooseCategory(category.slug)">{{ category.name }}</button>
      </div>
      <p v-if="!categories.length" class="catalog-navigation__empty">暂无分类</p>
    </section>

    <Teleport to="body">
      <span v-if="tooltip" class="catalog-navigation__tooltip" :class="{ 'catalog-navigation__tooltip--above': tooltip.above }" :style="{ left: `${tooltip.x}px`, top: `${tooltip.y}px` }" aria-hidden="true">{{ tooltip.label }}</span>
    </Teleport>
  </nav>
</template>

<style scoped lang="scss">
.catalog-navigation {
  position: fixed;
  inset: var(--catalog-header-height, 60px) auto 0 0;
  z-index: 35;
  width: var(--catalog-rail-width, 56px);
  box-sizing: border-box;
  border-right: 1px solid #e9f5f2;
  color: #0d211d;
  background: #f3fcfa;
  font-family: var(--catalog-font, "Microsoft YaHei", "PingFang SC", sans-serif);
}

.catalog-navigation__items {
  display: flex;
  max-height: 100%;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  box-sizing: border-box;
  overflow: auto;
  padding: 12px 5px;
  scrollbar-width: none;
}
.catalog-navigation__items::-webkit-scrollbar { display: none; }

.catalog-navigation__button, .catalog-navigation__close {
  position: relative;
  display: grid;
  width: 44px;
  height: 44px;
  flex: 0 0 44px;
  place-items: center;
  border: 0;
  border-radius: 14px;
  padding: 0;
  color: #0d211d;
  background: transparent;
  font-size: 23px;
  cursor: pointer;
}
.catalog-navigation__button:hover, .catalog-navigation__close:hover { background: #e3f3ef; }
.catalog-navigation__button.is-active { color: #0d211d; background: #ddf4ee; }
.catalog-navigation__button.is-separated { margin-block-start: 13px; }
.catalog-navigation__button.is-separated::before { position: absolute; inset: -8px 7px auto; height: 1px; background: #dceee8; content: ""; }
.catalog-navigation button:focus-visible { outline: 2px solid var(--catalog-focus, #3b7864); outline-offset: 2px; }

.catalog-navigation__panel {
  position: absolute;
  inset: 12px auto auto calc(var(--catalog-rail-width, 56px) + 8px);
  width: min(280px, calc(100vw - var(--catalog-rail-width, 56px) - 24px));
  max-height: calc(100dvh - var(--catalog-header-height, 60px) - 24px);
  box-sizing: border-box;
  overflow: auto;
  border-radius: 12px;
  padding: 10px;
  background: var(--catalog-paper, #f7f7f2);
  box-shadow: 0 8px 24px #183c3426;
}
.catalog-navigation__panel-header { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding-left: 6px; }
.catalog-navigation__panel-header h2 { margin: 0; font-size: 15px; line-height: 1.4; }
.catalog-navigation__close { font-size: 18px; }
.catalog-navigation__categories { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 6px; margin-top: 8px; }
.catalog-navigation__category {
  min-width: 0;
  min-height: 44px;
  border: 0;
  border-radius: 7px;
  padding: 10px 8px;
  color: var(--catalog-ink, #183c34);
  background: #e8ede5;
  font: inherit;
  font-size: 14px;
  line-height: 1.4;
  overflow-wrap: anywhere;
  cursor: pointer;
}
.catalog-navigation__category:hover { background: #dce5dc; }
.catalog-navigation__category[aria-pressed="true"] { color: #fff; background: var(--catalog-jade, #3b7864); }
.catalog-navigation__empty { margin: 12px 6px 4px; color: #64766d; font-size: 13px; }
.catalog-navigation__tooltip {
  position: fixed;
  z-index: 100;
  max-width: calc(100vw - 16px);
  box-sizing: border-box;
  border-radius: 6px;
  padding: 7px 10px;
  color: #fff;
  background: #244e3f;
  font: 13px / 1.4 "Microsoft YaHei", "PingFang SC", sans-serif;
  white-space: nowrap;
  pointer-events: none;
  transform: translateY(-50%);
}
.catalog-navigation__tooltip--above { transform: translate(-50%, -100%); }

@media (max-width: 760px) {
  .catalog-navigation { inset: auto 8px calc(8px + env(safe-area-inset-bottom)) 8px; z-index: 40; width: auto; border: 1px solid #dceee8; border-radius: 16px; background: #f1faf8f5; box-shadow: 0 3px 18px #183c3418; }
  .catalog-navigation__items { max-height: none; flex-direction: row; justify-content: flex-start; gap: 4px; overflow-x: auto; overflow-y: hidden; padding: 6px; }
  .catalog-navigation__button { font-size: 23px; }
  .catalog-navigation__button.is-separated { margin-block-start: 0; margin-inline-start: 9px; }
  .catalog-navigation__button.is-separated::before { inset: 10px auto 10px -7px; width: 1px; height: auto; }
  .catalog-navigation__panel { position: fixed; inset: auto 8px calc(74px + env(safe-area-inset-bottom)) 8px; width: auto; max-height: min(60dvh, 440px); }
}
</style>
