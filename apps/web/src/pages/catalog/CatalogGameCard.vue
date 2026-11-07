<script setup lang="ts">
import { StarFilled, StarOutlined } from "@ant-design/icons-vue";
import { onMounted, onUnmounted, ref } from "vue";

const props = withDefaults(defineProps<{
  title: string;
  href: string;
  cover: string | null;
  /** 分类、热度、作者和站内标记只随目录数据保留，卡片不展示。 */
  categoryName?: string | null;
  authorName?: string | null;
  siteHosted?: boolean;
  heat?: number;
  wanted: boolean;
  featured?: boolean;
  eager?: boolean;
  /** 只为当前首张关键封面提权，不改变其他卡片默认加载策略。 */
  highPriority?: boolean;
}>(), { categoryName: null, authorName: null, siteHosted: false, heat: 0, featured: false, eager: false, highPriority: false });

const emit = defineEmits<{
  open: [event: MouseEvent];
  toggleWanted: [];
  coverMeasured: [cover: string, aspect: number];
}>();

function measureCover(event: Event): void {
  const image = event.currentTarget as HTMLImageElement;
  if (props.cover && image.naturalWidth > 0 && image.naturalHeight > 0) {
    emit("coverMeasured", props.cover, image.naturalWidth / image.naturalHeight);
  }
}

const card = ref<HTMLElement | null>(null);
const touchActionsOpen = ref(false);
const keyboardActionsOpen = ref(false);
let holdTimer: ReturnType<typeof setTimeout> | undefined;
let touchOrigin: { x: number; y: number } | undefined;
let suppressHoldClick = false;
function cancelHold(): void {
  if (holdTimer) clearTimeout(holdTimer);
  holdTimer = undefined;
  touchOrigin = undefined;
}

function startHold(event: PointerEvent): void {
  if (event.pointerType !== "touch") return;
  suppressHoldClick = false;
  if (event.target instanceof Element && event.target.closest("button")) return;
  cancelHold();
  touchOrigin = { x: event.clientX, y: event.clientY };
  holdTimer = setTimeout(() => {
    touchActionsOpen.value = true;
    suppressHoldClick = true;
    holdTimer = undefined;
  }, 550);
}

function moveHold(event: PointerEvent): void {
  if (touchOrigin && Math.hypot(event.clientX - touchOrigin.x, event.clientY - touchOrigin.y) > 10) cancelHold();
}

function open(event: MouseEvent): void {
  if (suppressHoldClick) {
    event.preventDefault();
    suppressHoldClick = false;
    return;
  }
  emit("open", event);
}

function closeTouchActions(event: Event): void {
  if (event.target instanceof Node && !card.value?.contains(event.target)) {
    touchActionsOpen.value = false;
    suppressHoldClick = false;
    cancelHold();
  }
}

function handleContextMenu(event: MouseEvent): void {
  if (touchActionsOpen.value || touchOrigin) event.preventDefault();
}

function revealKeyboardFocus(event: FocusEvent): void {
  if (event.target instanceof Element && event.target.matches(":focus-visible")) keyboardActionsOpen.value = true;
}

function releaseKeyboardFocus(event: FocusEvent): void {
  if (event.relatedTarget instanceof Node && card.value?.contains(event.relatedTarget)) return;
  // Keep controls focusable throughout Tab's transition from the link to a sibling button.
  queueMicrotask(() => {
    if (!card.value?.contains(document.activeElement)) keyboardActionsOpen.value = false;
  });
}

onMounted(() => document.addEventListener("pointerdown", closeTouchActions));
onUnmounted(() => {
  cancelHold();
  document.removeEventListener("pointerdown", closeTouchActions);
});
</script>

<template>
  <article ref="card" class="catalog-card" :class="{ 'catalog-card--featured': featured, 'catalog-card--touch-actions': touchActionsOpen, 'catalog-card--keyboard-actions': keyboardActionsOpen }" tabindex="-1" @pointerdown="startHold" @pointermove="moveHold" @pointerup="cancelHold" @pointercancel="cancelHold" @contextmenu="handleContextMenu" @focusin="revealKeyboardFocus" @focusout="releaseKeyboardFocus" @keydown.esc="touchActionsOpen = false">
    <a class="catalog-card__open" :href="href" target="_blank" rel="noopener noreferrer" :aria-label="`打开${title}`" @click="open" @auxclick="open">
      <span class="catalog-card__cover">
        <img v-if="cover" :src="cover" alt="" :loading="eager ? 'eager' : 'lazy'" :fetchpriority="highPriority ? 'high' : undefined" decoding="async" @load="measureCover" />
        <span v-else class="catalog-card__missing">{{ title }}</span>
      </span>
      <span class="catalog-card__mobile-name" :title="title">{{ title }}</span>
      <span v-if="featured" class="catalog-card__play" aria-hidden="true">开始游戏</span>
    </a>
    <div class="catalog-card__details">
      <h3>{{ title }}</h3>
    </div>
    <button type="button" class="catalog-card__wanted" :class="{ 'is-active': wanted }" :aria-pressed="wanted" :aria-label="`${wanted ? '移除想玩' : '加入想玩'}：${title}`" :title="wanted ? '移除想玩' : '加入想玩'" @click.stop="emit('toggleWanted')"><StarFilled v-if="wanted" aria-hidden="true" /><StarOutlined v-else aria-hidden="true" /></button>
  </article>
</template>

<style scoped lang="scss" src="./CatalogGameCard.scss"></style>
