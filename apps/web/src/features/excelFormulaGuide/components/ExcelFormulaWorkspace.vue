<script setup lang="ts">
import { computed, defineAsyncComponent, defineComponent, h, nextTick, onBeforeUnmount, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ArrowLeftOutlined, CheckOutlined, CopyOutlined, DownloadOutlined, SearchOutlined } from "@ant-design/icons-vue";

import { formulaLessons, formulaTaskGroups, practiceSheets } from "@/features/excelFormulaGuide/content";
import { PRACTICE_WORKBOOK_URL } from "@/features/excelFormulaGuide/model";
import { searchFormulaLessons, searchOnlineOperations } from "@/features/excelFormulaGuide/search";
import type { OnlineOperationId } from "@/features/excelFormulaGuide/onlineOperations";
import type { OperationOptions } from "@/features/excelFormulaGuide/localProcessingModel";
import UiButton from "@/shared/ui/Button.vue";
import SiteNavigation from "@/shared/ui/SiteNavigation.vue";
import ExcelLocalProcessor from "./ExcelLocalProcessor.vue";
import ListCompareOperator from "@/features/listCompare/components/ListCompareOperator.vue";

// 公式试算为新功能独立懒加载，旧教程/复制/文件清理不要求计算模块先加载成功。
const FormulaTrialPanel = defineAsyncComponent({
  loader: () => import("./FormulaTrialPanel.vue"), timeout: 15_000,
  loadingComponent: defineComponent({ setup: () => () => h("p", { class: "formula-preview-note" }, "正在加载本地试算面板…") }),
  errorComponent: defineComponent({ setup: () => () => h("p", { role: "alert" }, "试算模块未能加载，请刷新页面重试。") }),
});

const localOpen = ref(false);
const activeOperationTab = ref<"compare" | "workbook">("compare");
const localOperation = ref<OperationOptions["kind"]>("clean");
const lessonOperations: Partial<Record<string, OperationOptions["kind"]>> = {
  "trim-name": "clean",
  "unique-employees": "dedupe",
  "person-total": "sum",
  "condition-count": "count",
};

const route = useRoute();
const router = useRouter();
const search = ref("");
const hasSearch = computed(() => search.value.trim() !== "");
const matchedOperations = computed(() => searchOnlineOperations(search.value));
const category = ref("");
const taskId = ref("");
const lessonHeading = ref<HTMLElement | null>(null);
const taskResultsHeading = ref<HTMLElement | null>(null);
const copyState = ref<"idle" | "copying" | "copied" | "failed">("idle");
let copyGeneration = 0;
let copyResetTimer: ReturnType<typeof setTimeout> | undefined;

// 查询参数只接受已知教程；分享链接和刷新使用同一份目录，非法值回到第一篇。
const selectedLesson = computed(() => {
  const requested = typeof route.query.lesson === "string" ? route.query.lesson : "";
  return formulaLessons.find((lesson) => lesson.id === requested) ?? formulaLessons[0];
});
const relatedLocalOperation = computed(() => lessonOperations[selectedLesson.value?.id ?? ""]);
const isCompareRelatedLesson = computed(() => {
  const id = selectedLesson.value?.id ?? "";
  return ["missing-submissions", "duplicate-id", "unique-employees"].includes(id);
});
watch(relatedLocalOperation, (kind) => { if (kind) localOperation.value = kind; }, { immediate: true });

async function openCompareOperator(): Promise<void> {
  localOpen.value = true;
  activeOperationTab.value = "compare";
  await nextTick();
  const panel = document.getElementById("excel-local-processor");
  panel?.focus({ preventScroll: true });
  panel?.scrollIntoView({ block: "start", behavior: "auto" });
}

async function openWorkbookProcessor(operation?: OperationOptions["kind"]): Promise<void> {
  localOpen.value = true;
  activeOperationTab.value = "workbook";
  if (operation) localOperation.value = operation;
  await nextTick();
  const panel = document.getElementById("excel-local-processor");
  panel?.focus({ preventScroll: true });
  panel?.scrollIntoView({ block: "start", behavior: "auto" });
}

watch(() => route.query.op, (op) => {
  if (op === "compare") {
    openCompareOperator();
  } else if (op === "clean" || op === "dedupe" || op === "sum" || op === "count") {
    openWorkbookProcessor(op as OperationOptions["kind"]);
  }
}, { immediate: true });

const categories = computed(() => [...new Set(formulaLessons.map((lesson) => lesson.category))]);
// 任务分组只筛选已有教程；推荐项沿用完整场景说明，避免要求用户先知道函数名。
const selectedTask = computed(() => formulaTaskGroups.find((task) => task.id === taskId.value));
const taskLessons = computed(() => formulaLessons.filter((lesson) => selectedTask.value?.lessonIds.includes(lesson.id)));

// 搜索始终覆盖完整目录；退出旧浏览条件，避免日期等旧分类暗中排除求和结果。
const filteredLessons = computed(() => searchFormulaLessons(formulaLessons, search.value, {
  category: category.value, taskLessonIds: selectedTask.value?.lessonIds,
}));
watch(search, (value) => { if (value.trim()) { category.value = ""; taskId.value = ""; } });

/** 打开已登记的在线操作；只使用现有浏览器本地工具，不发起文件上传。 */
async function openOnlineOperation(id: OnlineOperationId): Promise<void> {
  if (id === "compare") await openCompareOperator();
  else await openWorkbookProcessor(id);
}

/** 分类浏览是显式的新选择，退出文本搜索及旧任务，而不更改正在阅读的教程。 */
function selectCategory(value: string): void {
  search.value = "";
  category.value = value;
  taskId.value = "";
}
// 每篇只展示会用到的工作表，旧教程继续使用原来的三张表。
const availablePracticeSheets = computed(() => practiceSheets.filter((sheet) => (selectedLesson.value?.exampleSheets ?? ["数据", "名单", "练习"]).includes(sheet.name)));

/** 清理复制反馈并使旧异步操作失效，切换教程和离开页面时均适用。 */
function resetCopyState(): void {
  copyGeneration += 1;
  if (copyResetTimer !== undefined) {
    clearTimeout(copyResetTimer);
    copyResetTimer = undefined;
  }
  copyState.value = "idle";
}

// 前进、后退或分享地址切换到其他用途时，退出不兼容的任务筛选，保持目录与正文一致。
watch(() => selectedLesson.value?.id, (lessonId) => {
  resetCopyState();
  if (selectedTask.value && !selectedTask.value.lessonIds.includes(lessonId ?? "")) {
    taskId.value = "";
  }
});
onBeforeUnmount(resetCopyState);

/** 选择已知教程并更新分享地址；移动端同时把阅读位置带到教程标题。 */
async function selectLesson(lessonId: string): Promise<void> {
  resetCopyState();
  await router.push({ path: route.path, query: { ...route.query, lesson: lessonId }, hash: "" });
  await nextTick();
  if (selectedLesson.value?.id !== lessonId) return;
  lessonHeading.value?.focus({ preventScroll: true });
  lessonHeading.value?.scrollIntoView({ block: "start", behavior: "auto" });
}

/** 按目标选课；单篇任务直接打开，多篇任务定位候选列表供用户比较。 */
async function selectTask(id: string): Promise<void> {
  const task = formulaTaskGroups.find((item) => item.id === id);
  if (!task) return;
  search.value = "";
  category.value = "";
  taskId.value = task.id;
  const candidates = formulaLessons.filter((lesson) => task.lessonIds.includes(lesson.id));
  if (candidates.length === 1 && candidates[0]) {
    await selectLesson(candidates[0].id);
    return;
  }
  await nextTick();
  if (taskId.value !== task.id) return;
  taskResultsHeading.value?.focus({ preventScroll: true });
  taskResultsHeading.value?.scrollIntoView({ block: "start", behavior: "auto" });
}

/** 跳到用途相近的教程，同时清除原任务条件，保证新教程仍能在目录中找到。 */
async function openRelatedLesson(): Promise<void> {
  const related = selectedLesson.value?.relatedLesson;
  if (!related) return;
  resetFilters();
  await selectLesson(related.id);
}

/** 复制当前教程的原始公式；切课或卸载后不再写入旧操作的反馈。 */
async function copyFormula(): Promise<void> {
  const lesson = selectedLesson.value;
  if (!lesson || copyState.value === "copying") return;
  resetCopyState();
  const generation = copyGeneration;
  copyState.value = "copying";
  try {
    if (!navigator.clipboard?.writeText) {
      copyState.value = "failed";
      return;
    }
    await navigator.clipboard.writeText(lesson.formula);
    if (generation !== copyGeneration) return;
    copyState.value = "copied";
    copyResetTimer = setTimeout(() => {
      copyState.value = "idle";
      copyResetTimer = undefined;
    }, 2500);
  } catch {
    if (generation === copyGeneration) copyState.value = "failed";
  }
}

/** 清空检索条件，保留正在阅读的教程与分享地址。 */
function resetFilters(): void {
  search.value = "";
  category.value = "";
  taskId.value = "";
}

</script>

<template>
  <div class="formula-guide-shell">
    <header class="formula-site-header">
      <RouterLink class="formula-site-brand" :to="{ name: 'home' }" aria-label="平行线首页">
        <img src="/logo-lines-mark.png" alt="" width="48" height="42" />
        <strong>平行线</strong>
      </RouterLink>
      <a class="formula-back-link" href="https://tools.pingxingxian.space/"><ArrowLeftOutlined aria-hidden="true" /> 返回工具列表</a>
    </header>

    <main class="formula-guide" aria-labelledby="formula-guide-title">
      <header class="formula-intro">
        <div class="formula-intro__copy">
          <p class="formula-intro__label">办公工具 / 零基础教程</p>
          <h1 id="formula-guide-title">Excel 公式速查</h1>
          <p class="formula-intro__description">搜索你要解决的问题或公式名，直接在线处理，或查看可复制的公式。</p>
        </div>
        <div class="formula-intro__practice">
          <div class="formula-intro__actions">
            <UiButton tone="ghost" :href="PRACTICE_WORKBOOK_URL" download="excel-formula-practice.xlsx" class="formula-download">
              <template #icon><DownloadOutlined aria-hidden="true" /></template>
              下载练习表
            </UiButton>
          </div>
          <p>{{ formulaLessons.length }} 篇教程共用一份 Excel<br />示例数据已填好，公式留给你练习。</p>
        </div>
      </header>

      <section id="formula-discovery" class="formula-search-hub" aria-labelledby="formula-search-title">
        <h2 id="formula-search-title">查功能、找公式</h2>
        <label class="formula-search-label" for="formula-search">输入工作需求或公式名</label>
        <div class="formula-search">
          <SearchOutlined aria-hidden="true" />
          <input id="formula-search" v-model="search" type="search" aria-label="搜索功能或公式" placeholder="按人员汇总、查找重复项、核对提交名单" autocomplete="off" />
        </div>
        <div class="formula-search-feedback"><p class="formula-search-count" aria-live="polite">{{ matchedOperations.length }} 个在线功能<span v-if="hasSearch"> · {{ filteredLessons.length }} 篇公式教程</span><span v-else> · {{ formulaLessons.length }} 篇公式教程可搜索</span></p><button v-if="hasSearch" type="button" @click="resetFilters">清空搜索</button></div>
        <section v-if="matchedOperations.length" class="formula-online-results" aria-labelledby="formula-online-title">
          <h3 id="formula-online-title">直接在线处理</h3>
          <div class="formula-online-grid">
            <button v-for="operation in matchedOperations" :key="operation.id" type="button" :aria-label="`在线处理：${operation.title}`" @click="openOnlineOperation(operation.id)">
              <strong>{{ operation.title }} <span aria-hidden="true">→</span></strong>
              <span>{{ operation.description }}</span>
            </button>
          </div>
        </section>
        <nav v-if="hasSearch" class="formula-search-results" aria-label="公式教程目录">
          <h3>查看公式与用法</h3>
          <ul v-if="filteredLessons.length" class="formula-search-lessons">
            <li v-for="lesson in filteredLessons" :key="lesson.id"><button type="button" @click="selectLesson(lesson.id)">
              <strong>{{ lesson.title }}</strong><span>{{ lesson.summary }}</span>
              <small>{{ lesson.functions.join(' + ') }} · {{ lesson.version }} · 查看公式 →</small>
            </button></li>
          </ul>
          <div v-else class="formula-search-empty"><p>没有找到相关教程，换个说法试试。</p><button type="button" @click="resetFilters">清空搜索和分类</button></div>
        </nav>
      </section>

      <section v-if="localOpen" id="excel-local-processor" class="excel-operations-panel" tabindex="-1" aria-label="本地操作面板">
        <div class="excel-operations-switch">
          <div class="excel-operations-tabs" role="tablist" aria-label="操作工具类型">
            <button type="button" role="tab" :aria-selected="activeOperationTab === 'compare'" class="excel-operations-tab" :class="{ 'is-active': activeOperationTab === 'compare' }" @click="activeOperationTab = 'compare'">两列名单查重比对</button>
            <button type="button" role="tab" :aria-selected="activeOperationTab === 'workbook'" class="excel-operations-tab" :class="{ 'is-active': activeOperationTab === 'workbook' }" @click="activeOperationTab = 'workbook'">表格文件处理 (.xlsx)</button>
          </div>
          <UiButton tone="ghost" class="excel-operations-close" @click="localOpen = false">收起操作</UiButton>
        </div>
        <div class="excel-operations-body"><ListCompareOperator v-if="activeOperationTab === 'compare'" /><ExcelLocalProcessor v-else :suggested-operation="localOperation" /></div>
      </section>

      <details class="formula-task-picker">
        <summary><h2 id="formula-task-title" tabindex="-1">按用途浏览 {{ formulaLessons.length }} 篇教程</h2><span>也可以从工作任务选起</span></summary>
        <div class="formula-tasks" role="group" aria-label="选择要完成的任务">
          <button v-for="task in formulaTaskGroups" :key="task.id" type="button" :aria-label="task.title" :aria-describedby="`task-description-${task.id}`" :aria-pressed="taskId === task.id" @click="selectTask(task.id)">
            <strong>{{ task.title }}</strong>
            <span :id="`task-description-${task.id}`">{{ task.description }}</span>
          </button>
        </div>
        <section v-if="selectedTask && taskLessons.length > 1" class="formula-task-results" :aria-labelledby="`task-results-${selectedTask.id}`" data-testid="task-recommendations">
          <div class="formula-task-results__heading">
            <h3 :id="`task-results-${selectedTask.id}`" ref="taskResultsHeading" tabindex="-1">{{ selectedTask.title }}</h3>
            <span>{{ taskLessons.length }} 篇教程</span>
          </div>
          <ul>
            <li v-for="lesson in taskLessons" :key="lesson.id">
              <button type="button" @click="selectLesson(lesson.id)">
                <strong>{{ lesson.title }} <span aria-hidden="true">→</span></strong>
                <span>{{ lesson.summary }}</span>
                <small>{{ lesson.version }}</small>
              </button>
            </li>
          </ul>
        </section>
      </details>

      <div class="formula-workspace" :class="{ 'is-searching': hasSearch }">
        <aside v-if="!hasSearch" class="formula-directory" aria-labelledby="lesson-directory">
          <div class="formula-directory__top">
            <h2 id="lesson-directory" tabindex="-1">你想完成什么？</h2>
            <div class="formula-categories" role="group" aria-label="教程分类">
              <button type="button" :aria-pressed="category === '' && taskId === ''" @click="selectCategory('')">全部</button>
              <!-- 手动切换分类时退出任务分组，避免两组分类条件互相排除。 -->
              <button v-for="item in categories" :key="item" type="button" :aria-pressed="category === item" @click="selectCategory(item)">{{ item }}</button>
            </div>
            <p class="formula-directory__count" aria-live="polite"><span v-if="selectedTask">{{ selectedTask.title }} · </span>{{ filteredLessons.length }} 篇教程</p>
          </div>
          <nav aria-label="公式教程目录">
          <ul v-if="filteredLessons.length" class="formula-lessons">
            <li v-for="lesson in filteredLessons" :key="lesson.id">
              <button type="button" class="formula-lesson-link" :class="{ 'is-selected': lesson.id === selectedLesson?.id }" :aria-current="lesson.id === selectedLesson?.id ? 'true' : undefined" @click="selectLesson(lesson.id)">
                <span class="formula-lesson-link__title">{{ lesson.title }}</span>
                <span class="formula-lesson-link__summary">{{ lesson.summary }}</span>
                <span class="formula-lesson-link__functions"><span v-if="lesson.functions.length">{{ lesson.functions.join(' + ') }} · </span>{{ lesson.version }}</span>
              </button>
            </li>
          </ul>
          <div v-else class="formula-search-empty">
            <p>没有找到相关教程，换个说法试试。</p>
            <button type="button" @click="resetFilters">清空搜索和分类</button>
          </div>
          </nav>
        </aside>

        <article v-if="selectedLesson" class="formula-article" aria-labelledby="lesson-title" data-testid="lesson-content">
          <header class="formula-article__header">
            <div class="formula-article__meta"><span>{{ selectedLesson.category }}</span><a href="#formula-discovery">返回搜索</a></div>
            <h2 id="lesson-title" ref="lessonHeading" tabindex="-1">{{ selectedLesson.title }}</h2>
            <p class="formula-article__summary">{{ selectedLesson.summary }}</p>
            <p class="formula-version">适用范围：{{ selectedLesson.version }} <a v-if="(selectedLesson.minExcelVersion ?? 2016) > 2016" href="#lesson-own-data-title">查看旧版替代方法</a></p>
            <div v-if="selectedLesson.selectionTip" class="formula-selection-tip" data-testid="lesson-selection-tip">
              <p>{{ selectedLesson.selectionTip }}</p>
              <button v-if="selectedLesson.relatedLesson" type="button" @click="openRelatedLesson">{{ selectedLesson.relatedLesson.label }} <span aria-hidden="true">→</span></button>
            </div>
          </header>

          <section class="formula-section" aria-labelledby="lesson-scenario-title">
            <h3 id="lesson-scenario-title">什么时候用</h3>
            <p>{{ selectedLesson.scenario }}</p>
            <div v-if="!localOpen" class="formula-scenario-actions">
              <UiButton v-if="isCompareRelatedLesson" tone="ghost" class="formula-local-entry" @click="openCompareOperator">直接在线查重比对两列</UiButton>
              <UiButton v-if="relatedLocalOperation" tone="ghost" class="formula-local-entry" @click="openWorkbookProcessor(relatedLocalOperation)">跟着教程处理自己的表格文件</UiButton>
            </div>
          </section>

          <section class="formula-section formula-recipe" aria-labelledby="lesson-formula-title" data-testid="formula-recipe">
            <div class="formula-section__heading"><h3 id="lesson-formula-title">复制这条公式</h3><span data-testid="paste-target">粘贴位置：{{ selectedLesson.sheetName }}表 {{ selectedLesson.targetCell }}</span></div>
            <pre class="formula-code" tabindex="0" aria-label="可选中并手动复制的 Excel 公式"><code data-testid="lesson-formula" v-text="selectedLesson.formula"></code></pre>
            <div class="formula-copy-row">
              <UiButton :disabled="copyState === 'copying'" :aria-busy="copyState === 'copying'" @click="copyFormula">
                <template #icon><CheckOutlined v-if="copyState === 'copied'" aria-hidden="true" /><CopyOutlined v-else aria-hidden="true" /></template>
                {{ copyState === 'copying' ? '复制中…' : copyState === 'copied' ? '已复制' : '复制公式' }}
              </UiButton>
              <p class="formula-copy-status" role="status" aria-live="polite">{{ copyState === 'failed' ? '复制失败，请选中公式手动复制。' : copyState === 'copied' ? '已复制' : '' }}</p>
            </div>
            <div class="formula-expected"><span>原始示例的固定参考答案</span><strong data-testid="expected-result">{{ selectedLesson.expected }}</strong><p>{{ selectedLesson.expectedValues ? '原始示例可和本题工作表 C 列逐行核对。网页修改输入后，请看本次试算结果。' : '原始示例可和练习表 D 列核对。网页修改输入后，请看本次试算结果。' }}</p></div>
          </section>

          <details class="formula-first-steps">
            <summary>第一次用 Excel？先看这几步</summary>
            <ol>
              <li>先下载上面的练习表，用 Excel 打开。底部的标签是不同工作表，点击本篇步骤指定的工作表名称即可切换。</li>
              <li>上方的 A、B、C 是列，左边的 1、2、3 是行。例如 <strong>C2</strong> 就是 C 列和第 2 行交叉的那一格。</li>
              <li>教程让你点击 C2 时，先单击那一格，再把公式粘贴进去。电脑上按 <kbd>Ctrl</kbd> + <kbd>V</kbd> 粘贴，按 <kbd>Enter</kbd> 确认。</li>
              <li>公式从 <code>=</code> 开始。直接使用复制按钮，保留公式中的英文逗号、括号和双引号。</li>
              <li>普通题在练习表 C 列输入，D 列是对照答案。新版筛选、去重、排序题在各自工作表的 A2 输入，C 列是对照答案。</li>
            </ol>
          </details>

          <FormulaTrialPanel :key="selectedLesson.id" :lesson="selectedLesson" :source-sheets="availablePracticeSheets" />



          <section class="formula-section" aria-labelledby="lesson-steps-title">
            <h3 id="lesson-steps-title">跟着做</h3>
            <ol class="formula-steps" data-testid="lesson-steps">
              <li v-for="(step, index) in selectedLesson.steps" :key="index"><h4>{{ step.title }}</h4><p>{{ step.detail }}</p></li>
            </ol>
          </section>

          <section class="formula-section" aria-labelledby="lesson-parts-title">
            <h3 id="lesson-parts-title">公式里每一部分是什么意思</h3>
            <dl class="formula-parts"><div v-for="(part, index) in selectedLesson.parts" :key="index"><dt><code>{{ part.fragment }}</code></dt><dd>{{ part.meaning }}</dd></div></dl>
          </section>

          <section class="formula-section" aria-labelledby="lesson-checks-title">
            <h3 id="lesson-checks-title">算完再核对一下</h3>
            <ul class="formula-checks"><li v-for="(check, index) in selectedLesson.checks" :key="index">{{ check }}</li></ul>
          </section>

          <section class="formula-section" aria-labelledby="lesson-own-data-title">
            <h3 id="lesson-own-data-title">换成你自己的表格</h3>
            <p>{{ selectedLesson.extension }}</p>
          </section>

          <section class="formula-section" aria-labelledby="lesson-pitfalls-title">
            <h3 id="lesson-pitfalls-title">结果不对，先查这里</h3>
            <div class="formula-pitfalls"><div v-for="(pitfall, index) in selectedLesson.pitfalls" :key="index"><h4>{{ pitfall.problem }}</h4><p>{{ pitfall.solution }}</p></div></div>
          </section>

          <footer class="formula-article__footer">
            <p>继续了解函数用法</p>
            <ul><li v-for="source in selectedLesson.sources" :key="source.url"><a :href="source.url" target="_blank" rel="noopener noreferrer">{{ source.title }} <span aria-hidden="true">↗</span><span class="formula-visually-hidden">，在新标签页打开</span></a></li></ul>
            <a class="formula-return-directory" href="#formula-discovery">回到搜索，查找下一个功能或公式</a>
          </footer>
        </article>
      </div>
    </main>
    <footer class="formula-site-footer"><SiteNavigation /></footer>
  </div>
</template>

<style scoped lang="scss" src="./ExcelFormulaWorkspace.scss"></style>

