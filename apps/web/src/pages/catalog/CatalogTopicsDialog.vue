<script setup lang="ts">
import { CloseOutlined, RightOutlined } from "@ant-design/icons-vue";
import { nextTick, ref } from "vue";

import { CATALOG_MORE_TOPICS, type CatalogTopicId } from "./catalogTopics";

defineProps<{
  selected: CatalogTopicId;
  counts: Readonly<Record<CatalogTopicId, number>>;
}>();
const emit = defineEmits<{ select: [id: CatalogTopicId] }>();
const dialog = ref<HTMLDialogElement | null>(null);
let trigger: HTMLElement | null = null;

async function open(event?: Event): Promise<void> {
  trigger = event?.currentTarget instanceof HTMLElement ? event.currentTarget : null;
  if (!dialog.value?.open) dialog.value?.showModal();
  await nextTick();
  const selected = dialog.value?.querySelector<HTMLButtonElement>('[aria-pressed="true"]');
  (selected ?? dialog.value?.querySelector<HTMLButtonElement>(".catalog-topics__choice"))?.focus();
}

function close(): void { dialog.value?.close(); }
function restoreFocus(): void { trigger?.focus(); }
function choose(id: CatalogTopicId): void {
  emit("select", id);
  close();
}

defineExpose({ open });
</script>

<template>
  <dialog ref="dialog" class="catalog-topics" aria-labelledby="catalog-topics-title" @close="restoreFocus">
    <header class="catalog-topics__heading"><h2 id="catalog-topics-title">更多专题</h2><button type="button" class="catalog-topics__close" aria-label="关闭专题" @click="close"><CloseOutlined aria-hidden="true" /></button></header>
    <div class="catalog-topics__choices">
      <button v-for="topic in CATALOG_MORE_TOPICS" :key="topic.id" type="button" class="catalog-topics__choice" :aria-pressed="selected === topic.id" @click="choose(topic.id)">
        <span class="catalog-topics__name">{{ topic.name }}<RightOutlined aria-hidden="true" /></span>
        <span class="catalog-topics__description">{{ topic.description }}</span>
        <span class="catalog-topics__count">{{ counts[topic.id] }} 款游戏</span>
      </button>
    </div>
  </dialog>
</template>

<style scoped lang="scss">
.catalog-topics { width: min(620px, calc(100vw - 32px)); max-height: 80dvh; box-sizing: border-box; overflow: auto; border: 1px solid #d0d9ce; border-radius: 12px; padding: 20px; color: var(--catalog-ink, #153a31); background: var(--catalog-paper, #f5f5ef); box-shadow: 0 18px 60px #143b3138; }
.catalog-topics::backdrop { background: #183c3470; }
.catalog-topics__heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 14px; }
.catalog-topics__heading h2 { margin: 0; font: 700 25px / 1.4 var(--catalog-heading-font, serif); }
.catalog-topics__close { display: grid; width: 44px; height: 44px; flex: 0 0 44px; place-items: center; border: 0; border-radius: 7px; color: inherit; background: #dfe7dc; cursor: pointer; }
.catalog-topics__choices { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.catalog-topics__choice { display: flex; min-height: 128px; min-width: 0; flex-direction: column; gap: 8px; align-items: stretch; border: 1px solid #cdd9cc; border-radius: 8px; padding: 15px; color: inherit; background: #e7ede2; text-align: left; cursor: pointer; }
.catalog-topics__choice:hover { border-color: #8baa99; background: #e1eadd; }
.catalog-topics__choice[aria-pressed="true"] { border-color: var(--catalog-jade, #3b7864); box-shadow: inset 0 0 0 1px var(--catalog-jade, #3b7864); }
.catalog-topics__name { display: flex; align-items: center; justify-content: space-between; gap: 8px; font: 700 19px / 1.4 var(--catalog-heading-font, serif); }
.catalog-topics__name .anticon { font-size: 12px; }
.catalog-topics__description { color: #5b6f62; font: 12px / 1.6 var(--catalog-font, sans-serif); }
.catalog-topics__count { margin-top: auto; color: #526c5a; font: 12px / 1.4 var(--catalog-font, sans-serif); }
.catalog-topics button:focus-visible { outline: 3px solid var(--catalog-focus, #3b7864); outline-offset: 3px; }
@media (max-width: 420px) {
  .catalog-topics { padding: 15px; }
  .catalog-topics__choices { grid-template-columns: 1fr; }
  .catalog-topics__choice { min-height: 112px; }
}
</style>
