<script setup lang="ts">
import { computed, onBeforeUnmount, ref, useId, watch } from "vue";

import type { CatalogAiRating } from "@/features/catalog/model";

const props = defineProps<{
  rating?: CatalogAiRating | null;
  gameName: string;
}>();

const dialog = ref<HTMLDialogElement | null>(null);
const trigger = ref<HTMLButtonElement | null>(null);
const detailsOpen = ref(false);
const dialogFont = ref<string>();
const instanceId = `catalog-ai-${useId()}`;
const titleId = `${instanceId}-title`;
const hasScore = computed(() => typeof props.rating?.score === "number"
  && Number.isFinite(props.rating.score) && props.rating.score >= 0 && props.rating.score <= 10);
const decimal = new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 });
const recordedDate = computed(() => props.rating?.evaluatedAt ?? props.rating?.reportedReviewDate ?? "");
const evaluatedDate = computed(() => {
  if (!props.rating?.evaluatedAt) {
    return props.rating?.reportedReviewDate?.replaceAll("-", "/") ?? "未提供";
  }
  const date = new Date(props.rating.evaluatedAt);
  return Number.isNaN(date.getTime()) ? "未记录" : date.toLocaleDateString("zh-CN", {
    year: "numeric", month: "2-digit", day: "2-digit", timeZone: "UTC",
  });
});
const sourceText = computed(() => props.rating?.sourceKind === "user_accepted_external_ai"
  ? "其他 AI 提供，用户采纳" : "独立 AI 评测");
const scopeLabels: Readonly<Record<string, string>> = {
  reported_description: "报告记录", independently_verified: "本站独立复核",
  scope: "试玩范围", summary: "试玩概况", completed: "完成情况", completion: "完成情况",
  minutes: "试玩时长", duration_minutes: "试玩时长", duration_seconds: "试玩时长",
  levels: "体验关卡", stages: "体验关卡", modes: "体验模式", sessions: "试玩次数",
  attempts: "尝试次数", actions: "体验内容", observed: "观察记录", tested: "体验内容",
  coverage: "覆盖范围", difficulty: "难度", device: "设备", input_methods: "操作方式",
  audio: "声音体验", sound: "声音体验",
};
const scopeValues: Readonly<Record<string, string>> = {
  keyboard: "键盘", mouse: "鼠标", touch: "触控", gamepad: "手柄",
  desktop: "桌面端", mobile: "移动端", not_tested: "未体验", unknown: "未知",
};

function readableValue(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return scopeValues[value] ?? value;
  if (typeof value === "number") return decimal.format(value);
  if (typeof value === "boolean") return value ? "是" : "否";
  if (Array.isArray(value)) return value.map(readableValue).filter(Boolean).join("、");
  if (typeof value === "object") return Object.values(value).map(readableValue).filter(Boolean).join("；");
  return "";
}

const scopeEntries = computed(() => Object.entries(props.rating?.playScope ?? {}).map(([key, value]) => {
  const text = readableValue(value);
  const unit = typeof value === "number"
    ? key === "minutes" || key === "duration_minutes" ? " 分钟" : key === "duration_seconds" ? " 秒" : ""
    : "";
  return { key, label: scopeLabels[key] ?? "", text: `${text}${unit}` };
}).filter((entry) => entry.text));

function dimensionScore(value: number | null): string {
  return value === null ? "未评" : decimal.format(value);
}

function openDetails(): void {
  if (!hasScore.value || !dialog.value || dialog.value.open) return;
  if (trigger.value) dialogFont.value = window.getComputedStyle(trigger.value).fontFamily;
  dialog.value.showModal();
  detailsOpen.value = true;
}

function closeDetails(): void {
  dialog.value?.close();
}

function onClosed(): void {
  // Restore the trigger while its expanded state still keeps the card overlay visible.
  if (trigger.value?.isConnected) trigger.value.focus({ preventScroll: true });
  detailsOpen.value = false;
}

function onBackdropClick(event: MouseEvent): void {
  const element = dialog.value;
  if (!element || event.target !== element) return;
  const bounds = element.getBoundingClientRect();
  if (event.clientX < bounds.left || event.clientX > bounds.right
    || event.clientY < bounds.top || event.clientY > bounds.bottom) closeDetails();
}

watch(() => props.rating?.assessmentId, () => closeDetails());
onBeforeUnmount(() => closeDetails());
</script>

<template>
  <span v-if="hasScore && rating" class="catalog-ai-rating"
    @pointerdown.stop @focusin.stop @click.stop @keydown.stop>
    <button ref="trigger" type="button" class="catalog-ai-rating__badge"
      aria-haspopup="dialog" :aria-controls="instanceId" :aria-expanded="detailsOpen"
      :aria-label="`查看${gameName}的AI评分详情，${rating.score?.toFixed(1)}分，满分10分`"
      @click="openDetails">
      <span>AI评分</span><strong>{{ rating.score?.toFixed(1) }}</strong><span class="catalog-ai-rating__out-of">/10</span>
    </button>
    <Teleport to="body">
      <dialog :id="instanceId" ref="dialog" class="catalog-ai-rating-dialog"
        :style="{ fontFamily: dialogFont }"
        :aria-labelledby="titleId" @close="onClosed" @cancel.stop
        @pointerdown.stop @focusin.stop @keydown.stop @click.stop="onBackdropClick">
        <header class="catalog-ai-rating-dialog__header">
          <div>
            <p class="catalog-ai-rating-dialog__eyebrow">AI评分</p>
            <h2 :id="titleId">{{ gameName }}</h2>
          </div>
          <button type="button" class="catalog-ai-rating-dialog__close" aria-label="关闭AI评分详情"
            autofocus @click="closeDetails"><span aria-hidden="true">×</span></button>
        </header>
        <div class="catalog-ai-rating-dialog__summary">
          <div class="catalog-ai-rating-dialog__total"><strong>{{ rating.score?.toFixed(1) }}</strong><span>/ 10</span></div>
          <div class="catalog-ai-rating-dialog__provenance">
            <span>{{ sourceText }}</span>
            <span>{{ rating.evaluatedAt ? '评测日期（UTC）' : '报告日期' }}<time v-if="recordedDate" :datetime="recordedDate">{{ evaluatedDate }}</time><span v-else> 未提供</span></span>
            <span v-if="!rating.evaluatedAt">具体时间未提供 · {{ rating.reportedTimezone ? `报告时区 ${rating.reportedTimezone}` : '时区未提供' }}</span>
            <span>游戏版本 {{ rating.gameVersion || '未知' }}</span>
          </div>
        </div>
        <section class="catalog-ai-rating-dialog__section" aria-label="各维度评分与权重">
          <h3>五维评分 <span>满分 10 分</span></h3>
          <ul class="catalog-ai-rating-dialog__dimensions">
            <li v-for="dimension in rating.dimensions" :key="dimension.key">
              <div class="catalog-ai-rating-dialog__dimension-name"><span>{{ dimension.label }}</span><small>权重 {{ decimal.format(dimension.weight * 100) }}%</small></div>
              <div class="catalog-ai-rating-dialog__dimension-value">
                <span class="catalog-ai-rating-dialog__track" aria-hidden="true"><span :style="{ width: `${Math.max(0, Math.min(10, dimension.score ?? 0)) * 10}%` }"></span></span>
                <strong>{{ dimensionScore(dimension.score) }}</strong>
              </div>
            </li>
          </ul>
        </section>
        <section class="catalog-ai-rating-dialog__section" aria-label="实际试玩范围">
          <h3>试玩范围</h3>
          <dl v-if="scopeEntries.length" class="catalog-ai-rating-dialog__scope">
            <template v-for="entry in scopeEntries" :key="entry.key">
              <dt v-if="entry.label">{{ entry.label }}</dt><dd :class="{ 'is-full': !entry.label }">{{ entry.text }}</dd>
            </template>
          </dl>
          <p v-else class="catalog-ai-rating-dialog__empty">未记录具体试玩范围。</p>
        </section>
        <section v-if="rating.limitations.length" class="catalog-ai-rating-dialog__section catalog-ai-rating-dialog__limits" aria-label="评测范围限制">
          <h3>评测说明</h3>
          <ul><li v-for="(limitation, index) in rating.limitations" :key="index">{{ limitation }}</li></ul>
        </section>
        <p class="catalog-ai-rating-dialog__footer">AI评分按记录的维度分与权重计算。</p>
      </dialog>
    </Teleport>
  </span>
</template>

<style scoped lang="scss">
.catalog-ai-rating {
  display: inline-flex;
  flex: 0 0 auto;
  vertical-align: middle;
}
.catalog-ai-rating__badge {
  pointer-events: auto;
  display: inline-flex;
  min-height: 28px;
  align-items: center;
  gap: 3px;
  border: 1px solid #38614f2e;
  border-radius: 5px;
  padding: 3px 6px;
  color: #244e3f;
  background: #edf2e8;
  font-family: var(--catalog-font, inherit);
  font-size: 10px;
  line-height: 1.25;
  white-space: nowrap;
  cursor: pointer;
  strong { font-size: 12px; font-variant-numeric: tabular-nums; }
  &:hover { border-color: #3b7864; background: #e2ecdf; }
}
.catalog-ai-rating__out-of { opacity: .75; }
.catalog-ai-rating__badge:focus-visible,
.catalog-ai-rating-dialog__close:focus-visible { outline: 3px solid #8ab6a2; outline-offset: 3px; }
.catalog-ai-rating-dialog {
  box-sizing: border-box;
  width: min(560px, calc(100vw - 32px));
  max-height: calc(100dvh - 32px);
  overflow-y: auto;
  margin: auto;
  border: 1px solid #d7dccf;
  border-radius: 16px;
  padding: 24px;
  color: #283d32;
  background: #f7f7f0;
  font-family: inherit;
  box-shadow: 0 20px 70px #1a362b38;
  &::backdrop { background: #142b215c; }
}
.catalog-ai-rating-dialog__header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  h2 { margin: 0; font-size: 22px; line-height: 1.45; overflow-wrap: anywhere; }
}
.catalog-ai-rating-dialog__eyebrow { margin: 0 0 5px; color: #58745f; font-size: 12px; letter-spacing: .06em; }
.catalog-ai-rating-dialog__close {
  display: grid;
  width: 44px;
  height: 44px;
  flex: 0 0 auto;
  place-items: center;
  margin: -8px -8px 0 0;
  border: 0;
  border-radius: 50%;
  color: #3a5745;
  background: transparent;
  font-family: inherit;
  font-size: 28px;
  line-height: 1;
  cursor: pointer;
  &:hover { background: #e9eddf; }
}
.catalog-ai-rating-dialog__summary {
  display: flex;
  align-items: center;
  gap: 24px;
  margin: 22px 0;
  border-bottom: 1px solid #dce1d4;
  padding-bottom: 22px;
}
.catalog-ai-rating-dialog__total {
  display: flex;
  flex: 0 0 auto;
  align-items: baseline;
  gap: 6px;
  color: #315f4e;
  font-variant-numeric: tabular-nums;
  strong { font-size: 44px; font-weight: 650; line-height: 1; letter-spacing: -.04em; }
  > span { color: #71806c; font-size: 14px; }
}
.catalog-ai-rating-dialog__provenance {
  display: grid;
  gap: 5px;
  color: #65715e;
  font-size: 12px;
  line-height: 1.6;
  overflow-wrap: anywhere;
  time { margin-left: 6px; font-variant-numeric: tabular-nums; }
}
.catalog-ai-rating-dialog__section {
  margin-top: 22px;
  h3 { display: flex; align-items: baseline; gap: 10px; margin: 0 0 12px; color: #314b3a; font-size: 14px; font-weight: 600; }
  h3 > span { color: #7c8572; font-size: 11px; font-weight: 400; }
}
.catalog-ai-rating-dialog__dimensions {
  display: grid;
  gap: 13px;
  margin: 0;
  padding: 0;
  list-style: none;
}
.catalog-ai-rating-dialog__dimension-name {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  font-size: 12px;
  small { color: #7a846f; font-size: 11px; white-space: nowrap; }
}
.catalog-ai-rating-dialog__dimension-value {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 6px;
  strong { min-width: 32px; color: #315f4e; font-size: 12px; font-weight: 600; font-variant-numeric: tabular-nums; text-align: right; }
}
.catalog-ai-rating-dialog__track {
  height: 5px;
  flex: 1;
  overflow: hidden;
  border-radius: 5px;
  background: #e2e7da;
  > span { display: block; height: 100%; border-radius: inherit; background: #6d9479; }
}
.catalog-ai-rating-dialog__scope {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 7px 14px;
  margin: 0;
  border-radius: 8px;
  padding: 13px;
  background: #ecefe4;
  font-size: 12px;
  line-height: 1.7;
  dt { color: #73816b; }
  dd { margin: 0; overflow-wrap: anywhere; }
  .is-full { grid-column: 1 / -1; }
}
.catalog-ai-rating-dialog__empty { color: #73816b; font-size: 12px; }
.catalog-ai-rating-dialog__limits {
  ul { display: grid; gap: 5px; margin: 0; padding-left: 17px; color: #6c7563; font-size: 12px; line-height: 1.7; }
}
.catalog-ai-rating-dialog__footer { margin: 22px 0 0; color: #7e8775; font-size: 11px; line-height: 1.7; }
@media (max-width: 760px) {
  .catalog-ai-rating__badge { min-height: 44px; }
  .catalog-ai-rating-dialog { padding: 20px; border-radius: 12px; }
  .catalog-ai-rating-dialog__summary { gap: 16px; }
  .catalog-ai-rating-dialog__total strong { font-size: 38px; }
}
</style>
