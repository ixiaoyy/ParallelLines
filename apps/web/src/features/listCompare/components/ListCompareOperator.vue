<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import { CopyOutlined, DownloadOutlined } from "@ant-design/icons-vue";

import {
  SAMPLE_LIST_A,
  SAMPLE_LIST_B,
  compareNameLists,
  explainCompareFailure,
  summarizeList,
  toClipboardText,
  toDownloadText,
  type CompareSuccess,
  type ListSummary,
} from "@/features/listCompare/compare";
import UiButton from "@/shared/ui/Button.vue";

interface ResultGroup {
  id: "both" | "only-a" | "only-b";
  title: string;
  filename: string;
  lines: string[];
}

const listA = ref("");
const listB = ref("");
const dedupe = ref(false);
const ignoreCase = ref(false);
const result = ref<CompareSuccess | null>(null);
const errorMessage = ref("");
const statusMessage = ref("");
const editedSinceCompare = ref(false);
const errorBox = ref<HTMLElement | null>(null);
const resultsHeading = ref<HTMLElement | null>(null);
const downloadUrls = new Set<string>();
let statusTimer: ReturnType<typeof setTimeout> | undefined;
let downloadTimer: ReturnType<typeof setTimeout> | undefined;

const options = computed(() => ({ dedupe: dedupe.value, ignoreCase: ignoreCase.value }));
const summaryA = computed(() => summarizeList(listA.value, options.value));
const summaryB = computed(() => summarizeList(listB.value, options.value));
const stale = computed(() => result.value !== null && editedSinceCompare.value);
const groups = computed<ResultGroup[]>(() => {
  if (!result.value) return [];
  return [
    { id: "both", title: "两边都有", filename: "两边都有.txt", lines: result.value.both },
    { id: "only-a", title: "仅 A 有", filename: "仅A有.txt", lines: result.value.onlyA },
    { id: "only-b", title: "仅 B 有", filename: "仅B有.txt", lines: result.value.onlyB },
  ];
});

watch([listA, listB, dedupe, ignoreCase], () => {
  editedSinceCompare.value = true;
}, { flush: "sync" });

function summaryText(summary: ListSummary): string {
  const parts = [`有效 ${summary.entries.length} 条`];
  if (summary.blankLines > 0) parts.push(`已忽略 ${summary.blankLines} 个空行`);
  if (dedupe.value && summary.removedDuplicates > 0) parts.push(`去重后 ${summary.prepared.length} 条`);
  return parts.join("，");
}

function setStatus(message: string): void {
  if (statusTimer !== undefined) clearTimeout(statusTimer);
  statusMessage.value = message;
  statusTimer = setTimeout(() => {
    statusMessage.value = "";
    statusTimer = undefined;
  }, 2500);
}

function releaseDownloads(): void {
  if (downloadTimer !== undefined) {
    clearTimeout(downloadTimer);
    downloadTimer = undefined;
  }
  for (const url of downloadUrls) URL.revokeObjectURL(url);
  downloadUrls.clear();
}

onBeforeUnmount(() => {
  if (statusTimer !== undefined) clearTimeout(statusTimer);
  releaseDownloads();
});

function fillExample(): void {
  listA.value = SAMPLE_LIST_A;
  listB.value = SAMPLE_LIST_B;
  result.value = null;
  errorMessage.value = "";
}

function clearAll(): void {
  listA.value = "";
  listB.value = "";
  result.value = null;
  errorMessage.value = "";
  statusMessage.value = "";
}

async function startCompare(): Promise<void> {
  const outcome = compareNameLists({
    listA: listA.value,
    listB: listB.value,
    dedupe: dedupe.value,
    ignoreCase: ignoreCase.value,
  });
  if (!outcome.ok) {
    result.value = null;
    errorMessage.value = explainCompareFailure(outcome);
    await nextTick();
    errorBox.value?.focus();
    return;
  }
  errorMessage.value = "";
  result.value = outcome;
  editedSinceCompare.value = false;
  await nextTick();
  resultsHeading.value?.focus({ preventScroll: true });
  resultsHeading.value?.scrollIntoView({ block: "start", behavior: "auto" });
}

async function copyGroup(group: ResultGroup): Promise<void> {
  if (group.lines.length === 0) return;
  const text = toClipboardText(group.lines);
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      setStatus(`已复制「${group.title}」，共 ${group.lines.length} 条。`);
      return;
    }
  } catch {
    // 剪贴板不可用时降级为手动选择
  }
  if (selectResult(group.id)) {
    setStatus(`已选中「${group.title}」，请按 Ctrl+C 复制。`);
    return;
  }
  setStatus("复制失败，请在结果里手动选择文本。");
}

function selectResult(id: ResultGroup["id"]): boolean {
  const resultBody = document.getElementById(`compare-result-body-${id}`);
  const selection = window.getSelection();
  if (!resultBody || !selection) return false;
  const range = document.createRange();
  range.selectNodeContents(resultBody);
  selection.removeAllRanges();
  selection.addRange(range);
  return selection.toString().length > 0;
}

function downloadGroup(group: ResultGroup): void {
  if (group.lines.length === 0) return;
  const url = URL.createObjectURL(new Blob([toDownloadText(group.lines)], { type: "text/plain;charset=utf-8" }));
  downloadUrls.add(url);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = group.filename;
  document.body.append(anchor);
  try {
    anchor.click();
  } finally {
    anchor.remove();
  }
  if (downloadTimer !== undefined) clearTimeout(downloadTimer);
  downloadTimer = setTimeout(() => {
    releaseDownloads();
  }, 1000);
  setStatus(`已开始下载「${group.title}」。`);
}
</script>

<template>
  <div class="list-compare-operator" aria-labelledby="compare-operator-title">
    <div class="list-compare-operator__heading">
      <div>
        <h3 id="compare-operator-title">两列名单查重比对</h3>
        <p>粘贴两列数据（可直接从 Excel 复制一列），找出共有重复项与各自独有的条目。</p>
      </div>
      <p class="list-compare-operator__privacy">数据仅在当前浏览器处理，不上传服务器。</p>
    </div>

    <fieldset class="list-compare-operator__options">
      <legend>核对选项</legend>
      <label><input v-model="dedupe" type="checkbox" />去重，相同条目只保留第一次出现</label>
      <label><input v-model="ignoreCase" type="checkbox" />忽略英文大小写，不影响中文和数字</label>
    </fieldset>

    <div class="list-compare-operator__columns">
      <div class="list-compare-operator__column">
        <label for="compare-list-a">名单 A</label>
        <textarea id="compare-list-a" v-model="listA" rows="10" spellcheck="false" autocomplete="off" autocapitalize="off" autocorrect="off" translate="no" placeholder="每行一条，可从 Excel 粘贴一列" :aria-describedby="errorMessage ? 'compare-error-msg' : 'compare-list-a-summary'"></textarea>
        <p id="compare-list-a-summary">{{ summaryText(summaryA) }}</p>
      </div>
      <div class="list-compare-operator__column">
        <label for="compare-list-b">名单 B</label>
        <textarea id="compare-list-b" v-model="listB" rows="10" spellcheck="false" autocomplete="off" autocapitalize="off" autocorrect="off" translate="no" placeholder="每行一条，可从 Excel 粘贴一列" :aria-describedby="errorMessage ? 'compare-error-msg' : 'compare-list-b-summary'"></textarea>
        <p id="compare-list-b-summary">{{ summaryText(summaryB) }}</p>
      </div>
    </div>

    <div class="list-compare-operator__actions">
      <UiButton @click="startCompare">开始核对</UiButton>
      <UiButton tone="subtle" @click="fillExample">填入示例</UiButton>
      <UiButton tone="ghost" @click="clearAll">清空</UiButton>
    </div>

    <p v-if="errorMessage" id="compare-error-msg" ref="errorBox" class="list-compare-operator__error" role="alert" tabindex="-1">{{ errorMessage }}</p>

    <div class="list-compare-operator__notes">
      <p>从 Excel 选中一列，复制后直接粘贴。默认去掉首尾空格、忽略空行；001 和 1 按原文区分。</p>
      <p>重复行按出现次数分别统计，并保持原来的先后顺序。A 有 2 次、B 有 1 次时，1 次列入两边都有，多出的 1 次列入仅 A 有。</p>
    </div>

    <section v-if="result" class="list-compare-operator__results" aria-labelledby="compare-results-title">
      <div class="list-compare-operator__results-head">
        <h4 id="compare-results-title" ref="resultsHeading" tabindex="-1">核对结果</h4>
        <p>名单 A {{ result.countA }} 条，名单 B {{ result.countB }} 条。结果按各自名单里的先后顺序排列。</p>
      </div>
      <p v-if="stale" class="list-compare-operator__stale" role="status">名单或选项已经改过，下面仍是上一次的结果。再次点击「开始核对」后更新。</p>
      <div class="list-compare-operator__groups">
        <article v-for="group in groups" :key="group.id" class="list-compare-operator__group" :aria-labelledby="`op-result-${group.id}`">
          <div class="list-compare-operator__group-top">
            <h5 :id="`op-result-${group.id}`">{{ group.title }} <span>{{ group.lines.length }} 条</span></h5>
            <div class="list-compare-operator__group-actions">
              <UiButton tone="subtle" :aria-label="`复制${group.title}`" :disabled="group.lines.length === 0" @click="copyGroup(group)"><CopyOutlined aria-hidden="true" /> 复制</UiButton>
              <UiButton tone="ghost" :aria-label="`下载${group.title}`" :disabled="group.lines.length === 0" @click="downloadGroup(group)"><DownloadOutlined aria-hidden="true" /> 下载 TXT</UiButton>
            </div>
          </div>
          <pre v-if="group.lines.length" :id="`compare-result-body-${group.id}`" translate="no">{{ group.lines.join("\n") }}</pre>
          <p v-else class="list-compare-operator__group-empty">没有条目</p>
        </article>
      </div>
    </section>
    <p class="list-compare-operator__sr" role="status" aria-live="polite">{{ statusMessage }}</p>
  </div>
</template>

<style scoped lang="scss" src="./ListCompareOperator.scss"></style>
