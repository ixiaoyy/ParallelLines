<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef, watch } from "vue";
import UiButton from "@/shared/ui/Button.vue";
import type { DataSheet, LocalWorkbook, OperationOptions, OperationResult, PlainCell, TableData } from "../localProcessingModel";
import { buildTable, cellText, runOperation } from "../localOperations";
import { createWorkbookClient } from "../localWorkbookClient";

type OperationKind = OperationOptions["kind"];
const props = withDefaults(defineProps<{ suggestedOperation?: OperationKind }>(), { suggestedOperation: "clean" });
const client = createWorkbookClient();
const operationTitles: Record<OperationKind, string> = { clean: "清理空格与空行", dedupe: "按列去重", sum: "单条件求和", count: "单条件计数" };

function makeSample(): LocalWorkbook {
  return {
    sourceName: "示例数据",
    sheets: [{ name: "办公明细", warnings: [], rows: [
      ["工号", "姓名", "部门", "金额", "日期"],
      ["001", " 张三 ", "行政", "0.10", { date: "2026-10-01" }],
      ["002", "李四", "财务", 0.2, { date: "2026-10-02" }],
      ["001", "张三", "行政", "0.20", { date: "2026-10-03" }],
      [null, null, null, null, null],
      ["003", " 王五 ", "行政", null, { date: "2026-10-04" }],
    ] }],
  };
}

const workbook = shallowRef<LocalWorkbook | null>(makeSample());
const sourceMode = ref<"sample" | "file">("sample");
const sheetName = ref("办公明细");
const headerRow = ref(1);
const kind = ref<OperationKind>(props.suggestedOperation);
const cleanColumn = ref(-1);
const removeBlankRows = ref(true);
const dedupeColumns = ref<number[]>([0]);
const conditionColumn = ref(2);
const conditionValue = ref("行政");
const valueColumn = ref(3);
const result = shallowRef<OperationResult | null>(null);
const isReading = ref(false);
const isExporting = ref(false);
const error = ref("");
const downloadMessage = ref("");
const fileInput = ref<HTMLInputElement | null>(null);
let ioGeneration = 0;
let settingWorkbook = false;
const objectUrls = new Map<string, ReturnType<typeof setTimeout>>();

const activeSheet = computed(() => workbook.value?.sheets.find((sheet) => sheet.name === sheetName.value));
const blockedSheets = computed(() => workbook.value?.sheets.filter((sheet) => sheet.blockedReason) ?? []);
const tableState = computed<{ table: TableData | null; error: string }>(() => {
  if (!activeSheet.value || activeSheet.value.blockedReason) return { table: null, error: "" };
  try { return { table: buildTable(activeSheet.value, headerRow.value), error: "" }; }
  catch (cause) { return { table: null, error: readableError(cause) }; }
});
const originalTable = computed(() => tableState.value.table);
const columnOptions = computed(() => Array.from({ length: originalTable.value?.columnCount ?? 0 }, (_, index) => {
  const header = originalTable.value?.headers?.[index];
  return { index, label: `${columnLetter(index)} · ${header === undefined ? "无表头" : cellText(header).trim().slice(0, 40) || "无标题"}` };
}));
const originalPreview = computed(() => originalTable.value?.rows.slice(0, 20) ?? []);
const resultPreview = computed(() => result.value?.rows.slice(0, 20) ?? []);
const operationTitle = computed(() => operationTitles[kind.value]);
const canProcess = computed(() => Boolean(originalTable.value) && !isReading.value && (kind.value !== "dedupe" || dedupeColumns.value.length > 0));
const canDownload = computed(() => Boolean(result.value && !result.value.issues.length
  && ((result.value.kind !== "sum" && result.value.kind !== "count") || result.value.aggregate)) && !isReading.value && !isExporting.value);

function readableError(cause: unknown): string { return cause instanceof Error ? cause.message : "处理未完成，请重试。"; }
function columnLetter(index: number): string {
  let value = index + 1;
  let label = "";
  while (value > 0) { value -= 1; label = String.fromCharCode(65 + value % 26) + label; value = Math.floor(value / 26); }
  return label;
}
function displayCell(value: PlainCell | undefined): string { return value === undefined ? "" : cellText(value); }
function cancelIo(): void { ioGeneration += 1; client.cancel(); isReading.value = false; isExporting.value = false; }
function releaseDownloads(): void {
  objectUrls.forEach((timer, url) => { clearTimeout(timer); URL.revokeObjectURL(url); });
  objectUrls.clear();
}
function invalidateResult(): void {
  if (settingWorkbook) return;
  if (isExporting.value) cancelIo();
  result.value = null;
  error.value = "";
  downloadMessage.value = "";
}
function firstHeaderRow(sheet: DataSheet): number {
  const index = sheet.rows.findIndex((row) => row.some((cell) => cell !== null && (typeof cell !== "string" || cell.trim() !== "")));
  return index < 0 ? 0 : index + 1;
}
function setSheetDefaults(sheet: DataSheet): void {
  settingWorkbook = true;
  sheetName.value = sheet.name;
  headerRow.value = firstHeaderRow(sheet);
  cleanColumn.value = -1;
  removeBlankRows.value = true;
  dedupeColumns.value = [0];
  const width = sheet.rows.reduce((max, row) => Math.max(max, row.length), 0);
  conditionColumn.value = sourceMode.value === "sample" ? 2 : 0;
  valueColumn.value = sourceMode.value === "sample" ? 3 : Math.min(1, Math.max(0, width - 1));
  conditionValue.value = sourceMode.value === "sample" ? "行政" : "";
  settingWorkbook = false;
  result.value = null;
  error.value = "";
  downloadMessage.value = "";
}
function chooseSheet(event: Event): void {
  const name = (event.target as HTMLSelectElement).value;
  const sheet = workbook.value?.sheets.find((item) => item.name === name);
  if (!sheet || sheet.blockedReason) return;
  cancelIo();
  setSheetDefaults(sheet);
}
function useSample(): void {
  cancelIo();
  releaseDownloads();
  const sample = makeSample();
  workbook.value = sample;
  sourceMode.value = "sample";
  setSheetDefaults(sample.sheets[0]!);
  if (fileInput.value) fileInput.value.value = "";
}
function resetAll(): void { useSample(); kind.value = props.suggestedOperation; }

async function readFile(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  input.value = "";
  cancelIo();
  releaseDownloads();
  const ownGeneration = ioGeneration;
  result.value = null;
  error.value = "";
  downloadMessage.value = "";
  workbook.value = null;
  sourceMode.value = "file";
  if (!/\.xlsx$/i.test(file.name)) { error.value = "目前只支持 .xlsx 文件，请在 Excel 中另存为此格式。"; return; }
  if (file.size === 0 || file.size > 5 * 1024 * 1024) { error.value = file.size === 0 ? "文件为空，请重新选择。" : "文件超过 5 MB，请缩小后再试。"; return; }
  isReading.value = true;
  try {
    const next = await client.read(file);
    if (ownGeneration !== ioGeneration) return;
    workbook.value = next;
    const firstUsable = next.sheets.find((sheet) => !sheet.blockedReason);
    if (firstUsable) setSheetDefaults(firstUsable);
    else { sheetName.value = ""; error.value = "此文件没有可处理的工作表。请查看下方原因。"; }
  } catch (cause) { if (ownGeneration === ioGeneration) error.value = readableError(cause); }
  finally { if (ownGeneration === ioGeneration) isReading.value = false; }
}

function processData(): void {
  if (!canProcess.value || !originalTable.value) return;
  invalidateResult();
  let options: OperationOptions;
  if (kind.value === "clean") options = { kind: "clean", columns: cleanColumn.value === -1 ? columnOptions.value.map((column) => column.index) : [cleanColumn.value], removeBlankRows: removeBlankRows.value };
  else if (kind.value === "dedupe") options = { kind: "dedupe", columns: [...dedupeColumns.value] };
  else if (kind.value === "sum") options = { kind: "sum", conditionColumn: conditionColumn.value, equals: conditionValue.value, valueColumn: valueColumn.value };
  else options = { kind: "count", conditionColumn: conditionColumn.value, equals: conditionValue.value };
  try { result.value = runOperation(originalTable.value, options); }
  catch (cause) { error.value = readableError(cause); }
}

async function downloadResult(): Promise<void> {
  const currentResult = result.value;
  const sheet = activeSheet.value;
  if (!canDownload.value || !currentResult || !sheet) return;
  cancelIo();
  const ownGeneration = ioGeneration;
  const baseName = (workbook.value?.sourceName ?? "表格").replace(/\.xlsx$/i, "").replace(/[<>:"/\\|?*\u0000-\u001f]/g, "_").slice(0, 60) || "表格";
  isExporting.value = true;
  error.value = "";
  downloadMessage.value = "";
  try {
    const buffer = await client.write(currentResult, sheet.name);
    if (ownGeneration !== ioGeneration || result.value !== currentResult) return;
    const url = URL.createObjectURL(new Blob([buffer], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${baseName}-${operationTitles[currentResult.kind]}-结果.xlsx`;
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    objectUrls.set(url, setTimeout(() => { URL.revokeObjectURL(url); objectUrls.delete(url); }, 30_000));
    downloadMessage.value = "结果文件已生成，原文件不会被覆盖。";
  } catch (cause) { if (ownGeneration === ioGeneration) error.value = readableError(cause); }
  finally { if (ownGeneration === ioGeneration) isExporting.value = false; }
}

watch(() => props.suggestedOperation, (next) => { kind.value = next; });
watch([kind, headerRow, cleanColumn, removeBlankRows, dedupeColumns, conditionColumn, conditionValue, valueColumn], invalidateResult, { deep: true, flush: "sync" });
onBeforeUnmount(() => {
  cancelIo();
  client.dispose();
  workbook.value = null;
  result.value = null;
  releaseDownloads();
});
</script>

<template>
  <section id="excel-local-processor" class="excel-local" tabindex="-1" aria-labelledby="excel-local-title">
    <div class="excel-local__heading">
      <div><h3 id="excel-local-title">用自己的表格试一试</h3><p>选择数据、设置操作，再核对结果并下载。</p></div>
      <UiButton tone="ghost" @click="resetAll">重置</UiButton>
    </div>
    <p class="excel-local__privacy">文件仅在当前浏览器处理，不上传。离开页面或重置后清除。</p>

    <div class="excel-local__source">
      <div class="excel-local__subheading"><h4>1. 选择数据</h4><UiButton tone="ghost" :aria-pressed="sourceMode === 'sample'" @click="useSample">使用示例数据</UiButton></div>
      <label for="excel-local-file" class="excel-local__label">选择本地 Excel 文件 <span>（.xlsx，最大 5 MB）</span></label>
      <input id="excel-local-file" ref="fileInput" type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" @change="readFile" />
      <p v-if="workbook" class="excel-local__source-name">当前数据：<strong>{{ workbook.sourceName }}</strong></p>
      <p v-if="isReading" role="status">正在读取文件…可以选择其他文件或重置。</p>
      <p v-if="error" class="excel-local__error" role="alert">{{ error }}</p>
      <details class="excel-local__limits">
        <summary>支持范围与导出说明</summary>
        <ul>
          <li>工作簿最多 10 张工作表、累计 100,000 格；每张表最多 5,000 行、50 列。每次处理其中一张。导出汇总表也计入累计上限。</li>
          <li>含公式、合并单元格、隐藏行列或错误单元格的工作表暂不支持。</li>
          <li>日期按文本导出。工号、前导零和长编号请在原文件中保存为文本；超过 15 位的数字编号不支持。</li>
          <li>下载的是所选工作表处理后的新值表，不保留原公式、样式、图片、其他工作表或表头前的内容。求和与计数另附汇总表。</li>
        </ul>
      </details>
      <ul v-if="blockedSheets.length" class="excel-local__blocked"><li v-for="sheet in blockedSheets" :key="sheet.name"><strong>{{ sheet.name }}</strong>：{{ sheet.blockedReason }}</li></ul>
    </div>

    <template v-if="workbook && activeSheet && !activeSheet.blockedReason">
      <fieldset class="excel-local__settings" :disabled="isReading">
        <legend>2. 设置操作</legend>
        <div class="excel-local__fields">
          <label>工作表<select :value="sheetName" @change="chooseSheet"><option v-for="sheet in workbook.sheets" :key="sheet.name" :value="sheet.name" :disabled="Boolean(sheet.blockedReason)">{{ sheet.name }}{{ sheet.blockedReason ? '（不支持）' : '' }}</option></select></label>
          <label>表头行号<input v-model.number="headerRow" type="number" min="0" :max="activeSheet.rows.length" step="1" inputmode="numeric" aria-describedby="excel-local-header-help" /></label>
        </div>
        <p id="excel-local-header-help" class="excel-local__help">填写原表中的行号；没有表头时填 0。只处理表头下方的数据。</p>
        <p v-if="tableState.error" class="excel-local__error" role="alert">{{ tableState.error }}</p>
        <ul v-if="activeSheet.warnings.length" class="excel-local__warnings"><li v-for="warning in activeSheet.warnings" :key="warning">{{ warning }}</li></ul>
        <label class="excel-local__operation">处理方式<select v-model="kind"><option value="clean">清理空格与空行</option><option value="dedupe">按列去重</option><option value="sum">单条件求和</option><option value="count">单条件计数</option></select></label>

        <template v-if="kind === 'clean'">
          <label>清理哪些列<select v-model.number="cleanColumn"><option :value="-1">全部列中的文本</option><option v-for="column in columnOptions" :key="column.index" :value="column.index">{{ column.label }}</option></select></label>
          <label class="excel-local__check"><input v-model="removeBlankRows" type="checkbox" /><span>同时移除全空行</span></label>
          <p class="excel-local__help">仅移除文本两端的空白，保留文字中间的空格；不改变数字和日期。</p>
        </template>
        <fieldset v-else-if="kind === 'dedupe'" class="excel-local__columns">
          <legend>根据哪些列判断重复</legend>
          <div class="excel-local__checks"><label v-for="column in columnOptions" :key="column.index" class="excel-local__check"><input v-model="dedupeColumns" type="checkbox" :value="column.index" /><span>{{ column.label }}</span></label></div>
          <p class="excel-local__help">至少选一列；所选列完全相同才重复，保留首次出现的行。区分大小写和数据类型，空值也参与判断。</p>
        </fieldset>
        <template v-else>
          <div class="excel-local__fields">
            <label>条件所在列<select v-model.number="conditionColumn"><option v-for="column in columnOptions" :key="column.index" :value="column.index">{{ column.label }}</option></select></label>
            <label>精确匹配的值<input v-model="conditionValue" type="text" placeholder="留空则匹配空值" autocomplete="off" /></label>
          </div>
          <p class="excel-local__help">按显示值精确匹配，区分大小写，不自动去空格，不支持通配符。</p>
          <label v-if="kind === 'sum'">求和数值列<select v-model.number="valueColumn"><option v-for="column in columnOptions" :key="column.index" :value="column.index">{{ column.label }}</option></select></label>
          <p v-if="kind === 'sum'" class="excel-local__help">支持普通十进制数，最多 12 位小数、30 位数字。空数值跳过；无效数值会列出位置，修正后才能下载。</p>
        </template>
        <div class="excel-local__actions"><UiButton :disabled="!canProcess" @click="processData">{{ operationTitle }}</UiButton><span>每次从原始数据处理，不累加上次结果。修改设置后请重新处理。</span></div>
      </fieldset>

      <div class="excel-local__previews">
        <div class="excel-local__preview">
          <h4>原始数据</h4><p class="excel-local__help">{{ originalTable?.rows.length ?? 0 }} 行数据，预览前 20 行。左侧为原表行号。</p>
          <div v-if="originalTable" class="excel-local__table-scroll" tabindex="0" role="region" aria-label="原始数据表，可横向滚动">
            <table><caption>{{ activeSheet.name }} · 原始数据</caption><thead><tr><th scope="col">原行号</th><th v-for="column in columnOptions" :key="column.index" scope="col">{{ column.label }}</th></tr></thead><tbody><tr v-for="(row, index) in originalPreview" :key="originalTable.rowNumbers[index]"><th scope="row">{{ originalTable.rowNumbers[index] }}</th><td v-for="column in columnOptions" :key="column.index">{{ displayCell(row[column.index]) }}</td></tr></tbody></table>
          </div>
          <p v-if="!originalTable?.rows.length" class="excel-local__empty">没有可预览的数据行，请核对表头位置。</p>
        </div>
        <div class="excel-local__preview">
          <h4>处理结果</h4><p class="excel-local__help">{{ result ? `${result.rows.length} 行数据，预览前 20 行。` : '处理后在这里核对结果。' }}<span v-if="result && (result.kind === 'sum' || result.kind === 'count')">表格展示命中条件的记录。</span></p>
          <div v-if="result" class="excel-local__table-scroll" tabindex="0" role="region" aria-label="处理结果表，可横向滚动">
            <table><caption>{{ activeSheet.name }} · 处理结果</caption><thead><tr><th scope="col">原行号</th><th v-for="column in columnOptions" :key="column.index" scope="col">{{ column.label }}</th></tr></thead><tbody><tr v-for="(row, index) in resultPreview" :key="result.rowNumbers[index]"><th scope="row">{{ result.rowNumbers[index] }}</th><td v-for="column in columnOptions" :key="column.index">{{ displayCell(row[column.index]) }}</td></tr></tbody></table>
          </div>
          <p v-if="!result" class="excel-local__empty">尚未处理。请选择操作并点击处理按钮。</p><p v-else-if="!result.rows.length" class="excel-local__empty">结果没有数据行。</p>
        </div>
      </div>

      <div v-if="result" class="excel-local__result" role="status" aria-live="polite">
        <h4>处理摘要</h4>
        <dl class="excel-local__counts"><div><dt>输入行</dt><dd>{{ result.summary.inputRows }}</dd></div><div><dt>结果行</dt><dd>{{ result.summary.outputRows }}</dd></div><div><dt>改动单元格</dt><dd>{{ result.summary.changedCells }}</dd></div><div><dt>删除行</dt><dd>{{ result.summary.removedRows }}</dd></div><div v-if="result.kind === 'sum' || result.kind === 'count'"><dt>命中行</dt><dd>{{ result.summary.matchedRows }}</dd></div><div v-if="result.kind === 'sum'"><dt>参与求和</dt><dd>{{ result.summary.usedNumericRows }}</dd></div><div v-if="result.kind === 'sum'"><dt>跳过空数值</dt><dd>{{ result.summary.blankNumericRows }}</dd></div></dl>
        <p v-if="result.aggregate" class="excel-local__aggregate">{{ result.kind === 'sum' ? '合计' : '计数' }}：<strong>{{ result.aggregate.value }}</strong><span v-if="result.kind === 'count'"> 行</span></p>
        <p v-if="result.aggregate?.notice" class="excel-local__help">{{ result.aggregate.notice }}</p>
      </div>
      <div v-if="result?.issues.length" class="excel-local__error" role="alert"><strong>发现 {{ result.issues.length }} 个异常，尚不能下载结果。</strong><ul><li v-for="(issue, index) in result.issues.slice(0, 20)" :key="index">原表第 {{ issue.row }} 行、第 {{ columnLetter(issue.column - 1) }} 列：{{ issue.message }}</li></ul><p v-if="result.issues.length > 20">仅展示前 20 项。请先在原文件中修正这些数值，再重新导入。</p></div>
      <div class="excel-local__actions excel-local__download"><UiButton :disabled="!canDownload" :loading="isExporting" @click="downloadResult">{{ isExporting ? '正在生成…' : '下载新的结果文件' }}</UiButton><span>原文件不会被覆盖；仅导出所选工作表的处理结果。</span></div>
      <p v-if="downloadMessage" role="status" class="excel-local__help">{{ downloadMessage }}</p>
    </template>
    <p v-else-if="!isReading && !workbook" class="excel-local__empty">选择一个 .xlsx 文件，或使用示例数据开始。</p>
  </section>
</template>

<style scoped src="./ExcelLocalProcessor.scss"></style>
