<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ArrowLeftOutlined, CheckOutlined, CopyOutlined, DownloadOutlined, SearchOutlined } from "@ant-design/icons-vue";

import { formulaLessons, formulaTaskGroups, practiceSheets } from "@/features/excelFormulaGuide/content";
import { PRACTICE_WORKBOOK_URL } from "@/features/excelFormulaGuide/model";
import { matchesLessonSearch } from "@/features/excelFormulaGuide/search";
import UiButton from "@/shared/ui/Button.vue";
import SiteNavigation from "@/shared/ui/SiteNavigation.vue";

const route = useRoute();
const router = useRouter();
const search = ref("");
const category = ref("");
const taskId = ref("");
const previewSheetName = ref("数据");
const previewViewport = ref<HTMLElement | null>(null);
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
const categories = computed(() => [...new Set(formulaLessons.map((lesson) => lesson.category))]);
// 任务分组只筛选已有教程；推荐项沿用完整场景说明，避免要求用户先知道函数名。
const selectedTask = computed(() => formulaTaskGroups.find((task) => task.id === taskId.value));
const taskLessons = computed(() => formulaLessons.filter((lesson) => selectedTask.value?.lessonIds.includes(lesson.id)));

// 日常问句和函数写法共用搜索，任务与分类决定当前检索范围。
const filteredLessons = computed(() => {
  return formulaLessons.filter((lesson) => {
    return (!selectedTask.value || selectedTask.value.lessonIds.includes(lesson.id))
      && (!category.value || lesson.category === category.value)
      && matchesLessonSearch(lesson, search.value);
  });
});
// 每篇只展示会用到的工作表，旧教程继续使用原来的三张表。
const availablePracticeSheets = computed(() => practiceSheets.filter((sheet) => (selectedLesson.value?.exampleSheets ?? ["数据", "名单", "练习"]).includes(sheet.name)));
const previewSheet = computed(() => availablePracticeSheets.value.find((sheet) => sheet.name === previewSheetName.value) ?? availablePracticeSheets.value[0]);
// 扩充后的练习表较长，预览只显示当前题目附近三行，并保留真实行号。
const previewRows = computed(() => {
  const sheet = previewSheet.value;
  if (!sheet) return [];
  const rows = sheet.rows.map((cells, index) => ({ cells, rowNumber: index + 2 }));
  if (sheet.name !== "练习" || rows.length <= 10) return rows;
  const targetRow = Number(selectedLesson.value?.targetCell.match(/\d+$/)?.[0] ?? 2);
  const start = Math.max(2, targetRow - 1);
  return rows.filter((row) => row.rowNumber >= start && row.rowNumber <= start + 2);
});

// 手机预览只横向定位蓝色目标格，不改变正文的纵向阅读位置。
watch([() => previewSheet.value?.name, () => selectedLesson.value?.id], async () => {
  await nextTick();
  const viewport = previewViewport.value;
  if (!viewport) return;
  const target = viewport.querySelector<HTMLElement>(".is-target");
  viewport.scrollLeft = target
    ? Math.max(0, viewport.scrollLeft + target.getBoundingClientRect().left - viewport.getBoundingClientRect().left - (viewport.clientWidth - target.offsetWidth) / 2)
    : 0;
}, { immediate: true, flush: "post" });

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

/** 将固定示例表的零起始列序号转换为表格列名。 */
function columnName(index: number): string {
  return String.fromCharCode(65 + index);
}

/** 标出当前教程要求填写的单元格；这里只展示固定数据，不执行公式。 */
function isTargetCell(sheetName: string, rowNumber: number, columnIndex: number): boolean {
  return selectedLesson.value?.sheetName === sheetName
    && selectedLesson.value.targetCell === `${columnName(columnIndex)}${rowNumber}`;
}
</script>

<template>
  <div class="formula-guide-shell">
    <header class="formula-site-header">
      <RouterLink class="formula-site-brand" :to="{ name: 'home' }" aria-label="平行线首页">
        <img src="/logo-lines-mark.png" alt="" width="48" height="42" />
        <strong>平行线</strong>
      </RouterLink>
      <RouterLink class="formula-back-link" :to="{ name: 'tools' }"><ArrowLeftOutlined aria-hidden="true" /> 返回工具列表</RouterLink>
    </header>

    <main class="formula-guide" aria-labelledby="formula-guide-title">
      <header class="formula-intro">
        <div class="formula-intro__copy">
          <p class="formula-intro__label">办公工具 / 零基础教程</p>
          <h1 id="formula-guide-title">Excel 公式速查</h1>
          <p class="formula-intro__description">先选你要解决的问题，再跟着步骤操作。<br />从点哪个格开始，直到算出正确结果。</p>
        </div>
        <div class="formula-intro__practice">
          <UiButton :href="PRACTICE_WORKBOOK_URL" download="excel-formula-practice.xlsx" class="formula-download">
            <template #icon><DownloadOutlined aria-hidden="true" /></template>
            下载练习表
          </UiButton>
          <p>{{ formulaLessons.length }} 篇教程共用一份 Excel<br />示例数据已填好，公式留给你练习。</p>
        </div>
      </header>

      <section class="formula-task-picker" aria-labelledby="formula-task-title">
        <h2 id="formula-task-title" tabindex="-1">不知道用哪个公式？先选你想得到的结果</h2>
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
      </section>

      <div class="formula-workspace">
        <aside class="formula-directory" aria-labelledby="lesson-directory">
          <div class="formula-directory__top">
            <h2 id="lesson-directory" tabindex="-1">你想完成什么？</h2>
            <label class="formula-search-label" for="formula-search">搜索问题或公式名</label>
            <div class="formula-search">
              <SearchOutlined aria-hidden="true" />
              <input id="formula-search" v-model="search" type="search" aria-label="搜索教程" placeholder="按人员汇总、查找重复项、核对提交名单" autocomplete="off" />
            </div>
            <div class="formula-categories" role="group" aria-label="教程分类">
              <button type="button" :aria-pressed="category === '' && taskId === ''" @click="category = ''; taskId = ''">全部</button>
              <!-- 手动切换分类时退出任务分组，避免两组分类条件互相排除。 -->
              <button v-for="item in categories" :key="item" type="button" :aria-pressed="category === item" @click="category = item; taskId = ''">{{ item }}</button>
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
            <div class="formula-article__meta"><span>{{ selectedLesson.category }}</span><a href="#formula-task-title">返回目录</a></div>
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

          <section class="formula-section" aria-labelledby="practice-preview-title">
            <div class="formula-section__heading"><h3 id="practice-preview-title">先认一下练习表</h3><span>固定示例数据</span></div>
            <div class="formula-sheet-tabs" role="group" aria-label="示例工作表">
              <button v-for="sheet in availablePracticeSheets" :key="sheet.name" type="button" :aria-pressed="previewSheet?.name === sheet.name" @click="previewSheetName = sheet.name">{{ sheet.name }}</button>
            </div>
            <template v-if="previewSheet">
              <p class="formula-sheet-description">{{ previewSheet.description }}</p>
              <div ref="previewViewport" class="formula-sheet-scroll" tabindex="0" :aria-label="`${previewSheet.name}工作表示例，可横向滚动`">
                <table class="formula-sheet">
                  <caption class="formula-visually-hidden">{{ previewSheet.name }}工作表，示例数据</caption>
                  <thead>
                    <tr class="formula-sheet__letters"><th scope="col" aria-label="行号"></th><th v-for="(_, index) in previewSheet.columns" :key="index" scope="col">{{ columnName(index) }}</th></tr>
                    <tr><th scope="row" class="formula-sheet__row-number">1</th><th v-for="(heading, index) in previewSheet.columns" :key="index" scope="col">{{ heading }}</th></tr>
                  </thead>
                  <tbody>
                    <tr v-for="row in previewRows" :key="row.rowNumber">
                      <th scope="row" class="formula-sheet__row-number">{{ row.rowNumber }}</th>
                      <td v-for="(cell, columnIndex) in row.cells" :key="columnIndex" :class="{ 'is-target': isTargetCell(previewSheet.name, row.rowNumber, columnIndex), 'is-number': typeof cell === 'number' }">
                        <span v-if="isTargetCell(previewSheet.name, row.rowNumber, columnIndex) && cell === ''" class="formula-sheet__placeholder">在此输入公式</span>
                        <span v-else>{{ cell }}</span>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <p v-if="previewSheet.name === '练习'" class="formula-preview-note">这里只预览当前题目附近的行，完整练习在下载文件中。</p>
            </template>
            <p class="formula-preview-note">这里用于对照位置；实际输入公式，请打开下载的 Excel 练习表。</p>
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
            <div class="formula-expected"><span>按回车后应该得到</span><strong data-testid="expected-result">{{ selectedLesson.expected }}</strong><p>{{ selectedLesson.expectedValues ? '和本题工作表 C 列逐行核对，自动展开区域里只输入一次公式。' : '和练习表 D 列的预期结果核对。' }}</p></div>
          </section>

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
            <a class="formula-return-directory" href="#formula-task-title">回到目录，选择下一个问题</a>
          </footer>
        </article>
      </div>
    </main>
    <footer class="formula-site-footer"><SiteNavigation /></footer>
  </div>
</template>

<style scoped lang="scss" src="./ExcelFormulaWorkspace.scss"></style>
