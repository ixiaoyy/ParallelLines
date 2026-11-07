<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import { ArrowLeftOutlined, CopyOutlined, DownloadOutlined } from "@ant-design/icons-vue";

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
import SiteNavigation from "@/shared/ui/SiteNavigation.vue";

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

// 输入或选项变化后保留上一次结果，并标明它已经过期，避免边改边丢结果。
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

/** 填入固定示例，方便直接看到重复项、空行、中文姓名和编号的核对方式。 */
function fillExample(): void {
  listA.value = SAMPLE_LIST_A;
  listB.value = SAMPLE_LIST_B;
  result.value = null;
  errorMessage.value = "";
}

/** 清空两份名单和结果。去重、大小写选项保留，方便下一次沿用。 */
function clearAll(): void {
  listA.value = "";
  listB.value = "";
  result.value = null;
  errorMessage.value = "";
  statusMessage.value = "";
}

/** 按当前文本和选项核对。空名单只提示，不生成三组空结果。 */
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
    // 剪贴板权限被拒绝时，改为选中页面上的结果，方便手动复制。
  }
  if (selectResult(group.id)) {
    setStatus(`浏览器没有直接写入剪贴板。已选中「${group.title}」，请按 Ctrl+C。`);
    return;
  }
  setStatus("复制失败，请在结果里手动选择文本。");
}

/** 选中某一组结果。文本框会把回车规范化，不能用来保留 Excel 需要的 CRLF。 */
function selectResult(id: ResultGroup["id"]): boolean {
  const resultBody = document.getElementById(`result-body-${id}`);
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
  <div class="list-compare-shell">
    <header class="list-compare-header">
      <RouterLink class="list-compare-brand" :to="{ name: 'home' }" aria-label="平行线首页">
        <img src="/logo-lines-mark.png" alt="" width="48" height="42" />
        <strong>平行线</strong>
      </RouterLink>
      <RouterLink class="list-compare-back" :to="{ name: 'tools' }"><ArrowLeftOutlined aria-hidden="true" /> 返回工具列表</RouterLink>
    </header>

    <main class="list-compare-page" aria-labelledby="list-compare-title">
      <header class="list-compare-intro">
        <div>
          <p class="list-compare-kicker">办公工具</p>
          <h1 id="list-compare-title">两份名单核对</h1>
          <p>粘贴两份名单，找出共有和各自独有的条目。</p>
        </div>
        <p class="list-compare-local">名单只在当前浏览器里处理，不会上传到服务器。</p>
      </header>

      <section class="list-compare-panel" aria-labelledby="list-compare-input-title">
        <h2 id="list-compare-input-title">输入两份名单</h2>
        <fieldset class="list-compare-options">
          <legend>核对选项</legend>
          <label><input v-model="dedupe" type="checkbox" />去重，相同条目只保留第一次出现</label>
          <label><input v-model="ignoreCase" type="checkbox" />忽略英文大小写，不影响中文和数字</label>
        </fieldset>

        <div class="list-compare-columns">
          <div class="list-compare-column">
            <label for="list-a">名单 A</label>
            <textarea id="list-a" v-model="listA" rows="12" spellcheck="false" autocomplete="off" autocapitalize="off" autocorrect="off" translate="no" placeholder="每行一条，可从 Excel 粘贴一列" :aria-describedby="errorMessage ? 'list-compare-error' : 'list-a-summary'"></textarea>
            <p id="list-a-summary">{{ summaryText(summaryA) }}</p>
          </div>
          <div class="list-compare-column">
            <label for="list-b">名单 B</label>
            <textarea id="list-b" v-model="listB" rows="12" spellcheck="false" autocomplete="off" autocapitalize="off" autocorrect="off" translate="no" placeholder="每行一条，可从 Excel 粘贴一列" :aria-describedby="errorMessage ? 'list-compare-error' : 'list-b-summary'"></textarea>
            <p id="list-b-summary">{{ summaryText(summaryB) }}</p>
          </div>
        </div>

        <div class="list-compare-actions">
          <UiButton @click="startCompare">开始核对</UiButton>
          <UiButton tone="subtle" @click="fillExample">填入示例</UiButton>
          <UiButton tone="ghost" @click="clearAll">清空</UiButton>
        </div>
        <p v-if="errorMessage" id="list-compare-error" ref="errorBox" class="list-compare-error" role="alert" tabindex="-1">{{ errorMessage }}</p>
        <div class="list-compare-notes">
          <p>从 Excel 选中一列，复制后直接粘贴。默认去掉首尾空格、忽略空行；001 和 1 按原文区分。</p>
          <p>重复行按出现次数分别统计，并保持原来的先后顺序。A 有 2 次、B 有 1 次时，1 次列入两边都有，多出的 1 次列入仅 A 有。</p>
        </div>
      </section>

      <section v-if="result" class="list-compare-results" aria-labelledby="list-compare-results-title">
        <div class="list-compare-results__heading">
          <h2 id="list-compare-results-title" ref="resultsHeading" tabindex="-1">核对结果</h2>
          <p>名单 A {{ result.countA }} 条，名单 B {{ result.countB }} 条。结果按各自名单里的先后顺序排列。</p>
        </div>
        <p v-if="stale" class="list-compare-stale" role="status">名单或选项已经改过，下面仍是上一次的结果。再次点击「开始核对」后更新。</p>
        <div class="list-compare-groups">
          <article v-for="group in groups" :key="group.id" class="list-compare-group" :aria-labelledby="`result-${group.id}`">
            <div class="list-compare-group__top">
              <h3 :id="`result-${group.id}`">{{ group.title }} <span>{{ group.lines.length }} 条</span></h3>
              <div class="list-compare-group__actions">
                <UiButton tone="subtle" :aria-label="`复制${group.title}`" :disabled="group.lines.length === 0" @click="copyGroup(group)"><CopyOutlined aria-hidden="true" /> 复制</UiButton>
                <UiButton tone="ghost" :aria-label="`下载${group.title}`" :disabled="group.lines.length === 0" @click="downloadGroup(group)"><DownloadOutlined aria-hidden="true" /> 下载 TXT</UiButton>
              </div>
            </div>
            <pre v-if="group.lines.length" :id="`result-body-${group.id}`" translate="no">{{ group.lines.join("\n") }}</pre>
            <p v-else class="list-compare-group__empty">没有条目</p>
          </article>
        </div>
      </section>
      <p class="list-compare-sr" role="status" aria-live="polite">{{ statusMessage }}</p>
    </main>
    <footer class="list-compare-footer"><SiteNavigation /></footer>
  </div>
</template>

<style scoped lang="scss" src="./ListCompareWorkspace.scss"></style>
