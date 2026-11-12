<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import type { FormulaLesson, PracticeSheet } from "../model";
import expandedPractice from "../expandedPractice.json";
import { createFormulaTrialClient } from "../formulaTrialClient";
import { createTrialSheets, FormulaTrialError, TRIAL_LIMITS, type TrialResult, type TrialSheet, type TrialValue } from "../formulaTrial";
import { formatTrialValue } from "../formulaTrialFormat";
import UiButton from "@/shared/ui/Button.vue";

const props = defineProps<{ lesson: FormulaLesson; sourceSheets: PracticeSheet[] }>();
const client = createFormulaTrialClient();
const sheets = ref<TrialSheet[]>(createTrialSheets(props.sourceSheets));
const formula = ref(props.lesson.formula);
const sheetName = ref(props.lesson.sheetName);
const viewport = ref<HTMLElement | null>(null);
const busy = ref(false);
const result = ref<TrialResult | null>(null);
const error = ref("");
const notice = ref("");
let generation = 0;

const activeSheet = computed(() => sheets.value.find((sheet) => sheet.name === sheetName.value) ?? sheets.value[0]);
const sheetDescription = computed(() => activeSheet.value?.name === "练习"
  ? "这里只显示当前题目附近的行。B 列可改输入，蓝格可改公式；参考列是原始示例答案。"
  : ["筛选练习", "去重练习", "排序练习"].includes(activeSheet.value?.name ?? "")
    ? "蓝格只输入一次，实际展开结果显示在上方本次计算结果中。C 列是原始示例的固定参考。"
    : props.sourceSheets.find((sheet) => sheet.name === activeSheet.value?.name)?.description ?? "");
const numberFormat = computed(() => expandedPractice.exercises.find((exercise) => exercise.id === props.lesson.id)?.numberFormat);
const outputText = computed(() => result.value?.values.map((row) => row.map((value) => formatTrialValue(value, numberFormat.value)).join(" | ")).join("\n") ?? "");
const targetRow = computed(() => Number(props.lesson.targetCell.match(/\d+$/)?.[0] ?? 2));
const rows = computed(() => {
  const source = activeSheet.value;
  if (!source) return [];
  const all = source.rows.slice(1).map((cells, index) => ({ cells, row: index + 2 }));
  return source.name === "练习" && all.length > 10
    ? all.filter((row) => row.row >= Math.max(2, targetRow.value - 1) && row.row <= targetRow.value + 1) : all;
});

function columnName(index: number): string { return String.fromCharCode(65 + index); }
function isTarget(row: number, column: number): boolean {
  return activeSheet.value?.name === props.lesson.sheetName && `${columnName(column)}${row}` === props.lesson.targetCell;
}
function editable(row: number, column: number): boolean {
  return activeSheet.value?.name !== "练习" ? !["筛选练习", "去重练习", "排序练习"].includes(activeSheet.value?.name ?? "")
    : row === targetRow.value && column === 1;
}
function inputType(row: number, column: number): "date" | "number" | "text" {
  if (activeSheet.value?.dateColumns.includes(column)) return "date";
  const initial = props.sourceSheets.find((sheet) => sheet.name === activeSheet.value?.name)?.rows[row - 2]?.[column];
  return typeof initial === "number" ? "number" : "text";
}

/** 输入修改立即终止旧 Worker 并清除旧结果，不能把上一次计算或参考答案当本次成功。 */
function invalidate(): void {
  const hadResult = result.value !== null || busy.value;
  generation += 1;
  client.cancel();
  busy.value = false;
  result.value = null;
  error.value = "";
  notice.value = hadResult ? "输入已修改，请重新试算。" : "";
}

/** 保留示例列的数值/文本/日期类型；空数值变为空格语义，工号等文本不猜成数字。 */
function changeCell(event: Event, row: number, column: number): void {
  if (!(event.target instanceof HTMLInputElement) || !activeSheet.value) return;
  invalidate();
  const text = event.target.value;
  const type = inputType(row, column);
  let value: TrialValue = text;
  if (type === "number") {
    value = text === "" ? null : Number(text);
    if (typeof value === "number" && !Number.isFinite(value)) { error.value = "请输入有效的数字。"; return; }
  }
  activeSheet.value.rows[row - 1]![column] = value;
}

/** 仅提交当前本题的字面数据；重建普通对象，避免把 Vue 代理或任何文件交给 Worker。 */
async function calculate(): Promise<void> {
  if (busy.value) return;
  const ownGeneration = ++generation;
  busy.value = true;
  error.value = "";
  notice.value = "";
  result.value = null;
  try {
    const next = await client.calculate({ formula: formula.value, sheetName: props.lesson.sheetName, targetCell: props.lesson.targetCell,
      sheets: sheets.value.map((sheet) => ({ name: sheet.name, dateColumns: [...sheet.dateColumns], rows: sheet.rows.map((row) => [...row]) })) });
    if (ownGeneration === generation) result.value = next;
  } catch (cause) {
    if (ownGeneration === generation) error.value = cause instanceof FormulaTrialError ? cause.message : "试算未完成，请重试。";
  } finally { if (ownGeneration === generation) busy.value = false; }
}

function cancel(): void { invalidate(); notice.value = "已停止本次试算。"; }
function reset(): void {
  invalidate();
  sheets.value = createTrialSheets(props.sourceSheets);
  formula.value = props.lesson.formula;
  sheetName.value = props.lesson.sheetName;
  notice.value = "已恢复本题原始示例。";
}
watch(formula, invalidate, { flush: "sync" });
watch(sheetName, async () => {
  await nextTick();
  const target = viewport.value?.querySelector<HTMLElement>(".is-target");
  if (viewport.value) viewport.value.scrollLeft = target
    ? Math.max(0, viewport.value.scrollLeft + target.getBoundingClientRect().left - viewport.value.getBoundingClientRect().left - (viewport.value.clientWidth - target.offsetWidth) / 2) : 0;
}, { immediate: true, flush: "post" });
onBeforeUnmount(() => { generation += 1; client.dispose(); });
</script>

<template>
  <section class="formula-trial" aria-labelledby="formula-trial-title">
    <div class="formula-trial__heading"><h3 id="formula-trial-title">直接在网页输入并试算</h3><UiButton tone="ghost" @click="reset">恢复原始示例</UiButton></div>
    <p class="formula-trial__privacy">只计算本题示例，不上传。可修改蓝色格公式及输入数据；切换教程或离开后清除改动。</p>
    <label class="formula-trial__formula-label" for="trial-formula">本次公式 · {{ lesson.sheetName }}!{{ lesson.targetCell }}</label>
    <textarea id="trial-formula" v-model="formula" :maxlength="TRIAL_LIMITS.formulaChars" rows="2" spellcheck="false" @keydown.ctrl.enter.prevent="calculate"></textarea>
    <div class="formula-trial__actions"><UiButton :disabled="busy" :loading="busy" @click="calculate">{{ busy ? '正在试算…' : '试算公式' }}</UiButton><UiButton v-if="busy" tone="ghost" @click="cancel">停止试算</UiButton><span>{{ lesson.sheetName }}!{{ lesson.targetCell }} · 本次结果不会覆盖参考答案</span></div>
    <p v-if="error" role="alert" class="formula-trial__error">{{ error }}</p>
    <p v-if="notice" class="formula-trial__notice" role="status">{{ notice }}</p>
    <div v-if="result" class="formula-trial__result" role="status" aria-live="polite">
      <h4>本次计算结果</h4><output data-testid="trial-result">{{ outputText }}</output>
      <p>{{ result.values.length }} 行 × {{ result.values[0]?.length }} 列<span v-if="numberFormat"> · 显示格式 {{ numberFormat }}<template v-if="result.values.length === 1"> · 原始值 {{ result.values[0]?.[0] }}</template></span></p>
    </div>
    <div class="formula-trial__tabs" role="group" aria-label="示例工作表"><button v-for="sheet in sheets" :key="sheet.name" type="button" :aria-pressed="activeSheet?.name === sheet.name" @click="sheetName = sheet.name">{{ sheet.name }}</button></div>
    <template v-if="activeSheet">
      <p class="formula-trial__help">{{ sheetDescription }}</p>
      <div ref="viewport" class="formula-sheet-scroll" tabindex="0" :aria-label="`${activeSheet.name}工作表示例，可横向滚动`">
        <table class="formula-sheet"><caption class="formula-trial__visually-hidden">{{ activeSheet.name }}工作表，可修改输入数据</caption><thead>
          <tr class="formula-sheet__letters"><th scope="col" aria-label="行号"></th><th v-for="(_, index) in activeSheet.rows[0]" :key="index" scope="col">{{ columnName(index) }}</th></tr>
          <tr><th scope="row" class="formula-sheet__row-number">1</th><th v-for="(heading, index) in activeSheet.rows[0]" :key="index" scope="col">{{ heading }}</th></tr>
        </thead><tbody><tr v-for="row in rows" :key="row.row"><th scope="row" class="formula-sheet__row-number">{{ row.row }}</th>
          <td v-for="(cell, column) in row.cells" :key="column" :class="{ 'is-target': isTarget(row.row, column) }">
            <input v-if="isTarget(row.row, column)" v-model="formula" :aria-label="`${activeSheet.name}!${columnName(column)}${row.row}公式`" type="text" :maxlength="TRIAL_LIMITS.formulaChars" placeholder="在此输入公式" spellcheck="false" @keydown.enter.prevent="calculate" />
            <input v-else-if="editable(row.row, column)" :type="inputType(row.row, column)" :value="cell ?? ''" :aria-label="`${activeSheet.name}!${columnName(column)}${row.row}`" :maxlength="TRIAL_LIMITS.valueChars" step="any" :min="inputType(row.row, column) === 'date' ? '1900-01-01' : undefined" :max="inputType(row.row, column) === 'date' ? '9999-12-31' : undefined" @input="changeCell($event, row.row, column)" />
            <span v-else>{{ cell }}</span>
          </td>
        </tr></tbody></table>
      </div>
      <p class="formula-trial__help">表格可横向滚动。蓝格可直接输入公式并按 Enter；文字工号仍按文字处理。参考答案是原示例的固定值。</p>
    </template>
    <details class="formula-trial__limits"><summary>试算范围与计算引擎</summary><p>支持本页教程的函数及有界单元格范围；不执行宏、JavaScript、网络函数或外链。公式最多 {{ TRIAL_LIMITS.formulaChars }} 字符、单范围 {{ TRIAL_LIMITS.rangeCells }} 格、每次 {{ TRIAL_LIMITS.timeoutMs / 1000 }} 秒，超限会明确停止；不支持完整 Excel 的隐藏行、格式及全部函数模式。</p><a href="/licenses/excel-formula-engine.txt" target="_blank" rel="noopener noreferrer">离线计算引擎许可说明</a></details>
  </section>
</template>

<style scoped lang="scss" src="./FormulaTrialPanel.scss"></style>
