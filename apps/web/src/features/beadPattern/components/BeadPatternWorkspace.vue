<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from "vue";
import { ArrowLeftOutlined, DownloadOutlined, PictureOutlined, ScissorOutlined, UndoOutlined } from "@ant-design/icons-vue";
import UiButton from "@/shared/ui/Button.vue";
import SiteNavigation from "@/shared/ui/SiteNavigation.vue";
import { ARTKAL_S_COLORS } from "../palette";
import { BEAD_MESSAGES, getMaterialCounts } from "../model";
import type { BeadPattern, CropRegion } from "../model";
import { getGridSize, loadBeadImage, sampleBeadImage } from "../image";
import type { LoadedImage } from "../image";
import { drawPattern } from "../render";
import { downloadMaterialsCsv, downloadPatternPng, printPattern } from "../exports";
import CropSelector from "./CropSelector.vue";

type View = "preview" | "chart" | "original";
type Tool = "inspect" | "paint" | "erase";
const palette = ARTKAL_S_COLORS;
const source = shallowRef<LoadedImage | null>(null);
const sourceName = ref("");
const crop = ref<CropRegion>({ x: 0, y: 0, width: 1, height: 1 });
const edge = ref(32);
const maxColors = ref(8);
const pattern = shallowRef<BeadPattern | null>(null);
const view = ref<View>("preview");
const tool = ref<Tool>("inspect");
const selectedColor = ref("S13");
const highlight = ref<string | null>(null);
const zoom = ref(100);
const error = ref("");
const loading = ref(false);
const generating = ref(false);
const exporting = ref(false);
const stale = ref(false);
const history = shallowRef<Array<Array<string | null>>>([]);
const generationCells = shallowRef<Array<string | null>>([]);
const canvas = ref<HTMLCanvasElement | null>(null);
const stage = ref<HTMLElement | null>(null);
const resultHeading = ref<HTMLElement | null>(null);
const fileInput = ref<HTMLInputElement | null>(null);
const stageWidth = ref(600);
const focusedCell = ref(0);
const canvasFocused = ref(false);
let layout = { cellSize: 12, offsetX: 0, offsetY: 0, width: 0, height: 0 };
let worker: Worker | null = null;
let workerTimer: ReturnType<typeof setTimeout> | undefined;
let drawFrame = 0;
let imageRequest = 0;
let disposed = false;
let observer: ResizeObserver | undefined;
let stroke: Array<string | null> | null = null;
let lastPaintIndex = -1;
const busy = computed(() => loading.value || generating.value);
const counts = computed(() => pattern.value ? getMaterialCounts(pattern.value, palette) : []);
const total = computed(() => counts.value.reduce((sum, item) => sum + item.count, 0));
const dimensions = computed(() => source.value ? getGridSize(source.value.image, crop.value, edge.value) : null);
const hasEdits = computed(() => !!pattern.value && pattern.value.cells.some((code, index) => code !== generationCells.value[index]));
const cellDescription = computed(() => {
  if (!pattern.value) return "";
  const index = Math.min(focusedCell.value, pattern.value.cells.length - 1);
  return `第 ${Math.floor(index / pattern.value.width) + 1} 行，第 ${index % pattern.value.width + 1} 列 · ${pattern.value.cells[index] ?? "空格"}`;
});
const selectedHex = computed(() => palette.find((color) => color.code === selectedColor.value)?.hex ?? "#000000");

/** 选择新图片只更新取景；已有图纸在成功重新生成前保留，并明确标记待更新。 */
async function selectImage(input: File | string, name: string) {
  if (busy.value) return;
  const request = ++imageRequest;
  loading.value = true;
  error.value = "";
  try {
    const loaded = await loadBeadImage(input);
    if (disposed || request !== imageRequest) { loaded.release(); return; }
    source.value?.release();
    source.value = loaded;
    sourceName.value = name;
    crop.value = { x: 0, y: 0, width: 1, height: 1 };
    stale.value = !!pattern.value;
  } catch (reason) {
    if (!disposed) error.value = reason instanceof Error ? reason.message : BEAD_MESSAGES.read;
  } finally {
    if (request === imageRequest) loading.value = false;
  }
}

/** 载入本站示例并采用适合该素材的格数，首次进入时不自动滚动页面。 */
async function useExample(kind: "pixel" | "portrait", initial = false) {
  if (busy.value) return;
  await selectImage(`/tools/bead-pattern/${kind === "pixel" ? "pixel-example.svg" : "portrait-example.png"}`, kind === "pixel" ? "盆栽示例" : "人像示例");
  if (error.value || disposed) return;
  edge.value = kind === "pixel" ? 32 : 64;
  maxColors.value = kind === "pixel" ? 8 : 24;
  await generate(!initial);
}
/** 通过文件选择框载入图片；清空输入以允许重选同一个文件。 */
async function onFile(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (file) await selectImage(file, file.name);
  input.value = "";
}
/** 只接收拖放的第一张本地图片，沿用同一文件校验入口。 */
async function onDrop(event: DragEvent) {
  const file = event.dataTransfer?.files[0];
  if (file) await selectImage(file, file.name);
}

/** 每次生成创建有时限的本地 Worker，成功后整体替换图纸，失败则保留现有成果。 */
async function generate(reveal = true) {
  if (!source.value || busy.value || disposed) return;
  if (hasEdits.value && !window.confirm(BEAD_MESSAGES.replace)) return;
  generating.value = true;
  error.value = "";
  try {
    const sampled = sampleBeadImage(source.value.image, crop.value, edge.value);
    const result = await new Promise<BeadPattern>((resolve, reject) => {
      worker = new Worker(new URL("../algorithm.worker.ts", import.meta.url), { type: "module" });
      workerTimer = setTimeout(() => reject(new Error("generation_timeout")), 20_000);
      worker.onerror = () => reject(new Error("generation_worker_failed"));
      worker.onmessage = (event: MessageEvent<{ id: number; pattern?: BeadPattern; error?: boolean }>) => {
        if (event.data.error || !event.data.pattern) reject(new Error("generation_failed"));
        else resolve(event.data.pattern);
      };
      worker.postMessage({ id: 1, width: sampled.width, height: sampled.height, data: sampled.data, maxColors: maxColors.value }, [sampled.data.buffer]);
    });
    if (disposed) return;
    pattern.value = result;
    generationCells.value = result.cells.slice();
    history.value = [];
    tool.value = "inspect";
    highlight.value = null;
    focusedCell.value = 0;
    view.value = "preview";
    zoom.value = 100;
    stale.value = false;
    selectedColor.value = getMaterialCounts(result, palette)[0]?.color.code ?? "S13";
    // 手机主动生成后将结果带入视野，初始示例不打断用户从顶部阅读。
    if (reveal && window.matchMedia("(max-width: 760px)").matches) {
      await nextTick();
      resultHeading.value?.scrollIntoView({ block: "start", behavior: "auto" });
    }
  } catch {
    if (!disposed) error.value = BEAD_MESSAGES.generate;
  } finally {
    clearTimeout(workerTimer);
    worker?.terminate();
    worker = null;
    generating.value = false;
  }
}

/** 只重绘画布，不改变底层格子；缩放、色号和高亮不会改变导出内容。 */
function redraw() {
  if (!canvas.value || !pattern.value || view.value === "original") return;
  const base = Math.min(16, Math.max(4, Math.floor((stageWidth.value - 80) / pattern.value.width)));
  const cellSize = view.value === "chart" ? 24 : base;
  layout = drawPattern(canvas.value, pattern.value, palette, {
    cellSize, grid: view.value === "chart", codes: view.value === "chart", coordinates: view.value === "chart",
    highlight: tool.value === "inspect" ? highlight.value : null,
  });
  // 放大只改变显示尺寸，128 格图纸在手机上也不会因三倍缩放创建九倍像素缓冲。
  canvas.value.style.width = `${layout.width * zoom.value / 100}px`;
  canvas.value.style.height = `${layout.height * zoom.value / 100}px`;
  if (canvasFocused.value) {
    const ctx = canvas.value.getContext("2d");
    const x = layout.offsetX + (focusedCell.value % pattern.value.width) * layout.cellSize;
    const y = layout.offsetY + Math.floor(focusedCell.value / pattern.value.width) * layout.cellSize;
    if (ctx) {
      ctx.strokeStyle = "#ffffff"; ctx.lineWidth = 3; ctx.strokeRect(x + 1.5, y + 1.5, cellSize - 3, cellSize - 3);
      ctx.strokeStyle = "#17202b"; ctx.lineWidth = 1; ctx.strokeRect(x + 1.5, y + 1.5, cellSize - 3, cellSize - 3);
    }
  }
}
/** 合并同一帧的连续绘制请求，避免逐格操作重复重绘整个画布。 */
function queueDraw() { cancelAnimationFrame(drawFrame); drawFrame = requestAnimationFrame(redraw); }

/** 通过画布实际像素换算点击位置，排除坐标标尺及空白边缘。 */
function indexAt(event: PointerEvent): number | null {
  if (!canvas.value || !pattern.value) return null;
  const rect = canvas.value.getBoundingClientRect();
  const x = Math.floor(((event.clientX - rect.left) * canvas.value.width / rect.width - layout.offsetX) / layout.cellSize);
  const y = Math.floor(((event.clientY - rect.top) * canvas.value.height / rect.height - layout.offsetY) / layout.cellSize);
  return x >= 0 && y >= 0 && x < pattern.value.width && y < pattern.value.height ? y * pattern.value.width + x : null;
}
/** 根据当前工具修改指定格，并连接同一笔画中的上一个格子。 */
function paint(index: number) {
  if (!pattern.value || tool.value === "inspect" || busy.value || index === lastPaintIndex) return;
  const code = tool.value === "erase" ? null : selectedColor.value;
  const width = pattern.value.width;
  const previous = lastPaintIndex < 0 ? index : lastPaintIndex;
  let x = previous % width;
  let y = Math.floor(previous / width);
  const endX = index % width;
  const endY = Math.floor(index / width);
  const dx = Math.abs(endX - x);
  const dy = -Math.abs(endY - y);
  const stepX = x < endX ? 1 : -1;
  const stepY = y < endY ? 1 : -1;
  let distance = dx + dy;
  const cells = pattern.value.cells.slice();
  let changed = false;
  // 连接同一笔画的前后触点，快速拖动跨过多个格子时也不会留下断点。
  for (let steps = 0; steps <= 128; steps++) {
    const current = y * width + x;
    if (cells[current] !== code) { cells[current] = code; changed = true; }
    if (x === endX && y === endY) break;
    const doubled = distance * 2;
    if (doubled >= dy) { distance += dy; x += stepX; }
    if (doubled <= dx) { distance += dx; y += stepY; }
  }
  if (changed) {
    if (!stroke) stroke = pattern.value.cells.slice();
    pattern.value = { ...pattern.value, cells };
  }
  lastPaintIndex = index;
}
/** 点按查看颜色或开始一笔编辑；只有画笔与橡皮捕获拖动事件。 */
function beginStroke(event: PointerEvent) {
  if (busy.value || event.button !== 0) return;
  const index = indexAt(event);
  if (index === null) return;
  focusedCell.value = index;
  if (tool.value === "inspect") { highlight.value = pattern.value!.cells[index]; return; }
  canvas.value?.setPointerCapture(event.pointerId);
  lastPaintIndex = -1;
  paint(index);
}
/** 将拖动触点转换为格子，离开图纸时中断连续线段。 */
function moveStroke(event: PointerEvent) {
  if (!canvas.value?.hasPointerCapture(event.pointerId)) return;
  const index = indexAt(event);
  if (index !== null) { focusedCell.value = index; paint(index); }
  else lastPaintIndex = -1;
}
/** 一次拖动作为一次撤销记录，最多保留三十次，避免长时间编辑占用无限内存。 */
function finishStroke() {
  if (stroke) history.value = [...history.value, stroke].slice(-30);
  stroke = null;
  lastPaintIndex = -1;
}
/** 恢复最近一次完整笔画前的网格，材料清单随网格重新计算。 */
function undo() {
  if (!pattern.value || busy.value) return;
  finishStroke();
  const cells = history.value.at(-1);
  if (!cells) return;
  history.value = history.value.slice(0, -1);
  pattern.value = { ...pattern.value, cells: cells.slice() };
}
/** 提供键盘定位与编辑，回车作用等同于点按当前格子。 */
function onCanvasKey(event: KeyboardEvent) {
  if (!pattern.value || busy.value) return;
  const { width, height } = pattern.value;
  const index = focusedCell.value;
  if (["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", " ", "Enter"].includes(event.key)) event.preventDefault();
  if (event.key === "ArrowLeft" && index % width > 0) focusedCell.value--;
  if (event.key === "ArrowRight" && index % width < width - 1) focusedCell.value++;
  if (event.key === "ArrowUp" && index >= width) focusedCell.value -= width;
  if (event.key === "ArrowDown" && index < width * (height - 1)) focusedCell.value += width;
  if (event.key === " " || event.key === "Enter") {
    if (tool.value === "inspect") highlight.value = pattern.value.cells[index];
    else { paint(index); finishStroke(); }
  }
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z") { event.preventDefault(); undo(); }
}
/** 切换编辑工具前结束当前笔画，原图视图切回可编辑图纸。 */
function selectTool(next: Tool) { finishStroke(); tool.value = next; highlight.value = null; if (view.value === "original") view.value = "chart"; }
/** 选择画笔颜色；查看工具下再次点击相同颜色可取消高亮。 */
function selectColor(code: string) { selectedColor.value = code; if (tool.value === "inspect") highlight.value = highlight.value === code ? null : code; }
/** 导出当前网格快照；失败只显示已确认提示，不丢弃编辑成果。 */
async function exportResult(kind: "preview" | "chart" | "csv" | "print") {
  if (!pattern.value || busy.value || exporting.value) return;
  exporting.value = true;
  error.value = "";
  try {
    if (kind === "csv") downloadMaterialsCsv(pattern.value, palette);
    else if (kind === "print") await printPattern(pattern.value, palette);
    else await downloadPatternPng(pattern.value, palette, kind);
  } catch { error.value = BEAD_MESSAGES.export; }
  finally { exporting.value = false; }
}
/** 将手填长边约束为整数格，清空时恢复默认值。 */
function clampEdge() { edge.value = Math.min(128, Math.max(8, Math.round(edge.value) || 48)); }

watch([edge, maxColors, crop], () => { if (pattern.value) stale.value = true; }, { deep: true, flush: "sync" });
watch([pattern, view, zoom, highlight, tool, focusedCell, canvasFocused, stageWidth], async () => { await nextTick(); queueDraw(); });
onMounted(() => {
  observer = new ResizeObserver((entries) => { stageWidth.value = entries[0]?.contentRect.width ?? 600; });
  if (stage.value) observer.observe(stage.value);
  void useExample("pixel", true);
});
onBeforeUnmount(() => {
  disposed = true; imageRequest++;
  worker?.terminate(); clearTimeout(workerTimer);
  cancelAnimationFrame(drawFrame); observer?.disconnect(); source.value?.release();
});
</script>

<template>
  <div class="bead-shell">
    <header class="bead-header"><RouterLink to="/tools" class="bead-brand"><img src="/logo-lines-mark.png" alt="" width="40" height="36" /><strong>平行线</strong></RouterLink><RouterLink to="/tools" class="bead-back"><ArrowLeftOutlined /> 返回工具</RouterLink></header>
    <main class="bead-page">
      <div class="bead-intro"><div><span class="bead-kicker">创作工具</span><h1>拼豆图纸生成器</h1><p>将图片转换为拼豆图纸，查看色号和用量。</p></div><span class="bead-local">图片仅在你的设备上处理</span></div>
      <div class="bead-workspace">
        <aside class="bead-settings" aria-label="图片与生成设置">
          <section class="bead-section">
            <h2><span>1</span> 选择图片</h2>
            <div class="bead-upload" @dragover.prevent @drop.prevent="onDrop">
              <input ref="fileInput" class="bead-file" type="file" accept="image/png,image/jpeg,image/webp" aria-label="选择图片" :disabled="busy" @change="onFile" />
              <UiButton tone="subtle" :disabled="busy" @click="fileInput?.click()"><PictureOutlined /> 选择图片</UiButton>
              <p>或将图片拖到这里</p><small>JPG / PNG / WebP · 最大 10 MB</small>
            </div>
            <div class="bead-examples"><button type="button" :disabled="busy" @click="useExample('pixel')"><img src="/tools/bead-pattern/pixel-example.svg" alt="" /><span>体验简单图案</span></button><button type="button" :disabled="busy" @click="useExample('portrait')"><img src="/tools/bead-pattern/portrait-example.png" alt="" /><span>体验人像</span></button></div>
            <div v-if="source" class="bead-source"><p class="bead-source__name" :title="sourceName">{{ sourceName }} <span>{{ source.image.naturalWidth }} × {{ source.image.naturalHeight }}</span></p><details class="bead-crop-panel"><summary>裁剪图片（可选）</summary><CropSelector v-model="crop" :src="source.url" :image-width="source.image.naturalWidth" :image-height="source.image.naturalHeight" :disabled="busy" /></details></div>
          </section>
          <section class="bead-section"><h2><span>2</span> 设置图纸</h2>
            <label class="bead-field-label" for="bead-edge">图纸长边 <span>一格对应一颗豆</span></label>
            <div class="bead-presets"><button v-for="size in [32, 48, 64]" :key="size" type="button" :aria-pressed="edge === size" :disabled="busy" @click="edge = size">{{ size }} 格</button><input id="bead-edge" v-model.number="edge" type="number" min="8" max="128" step="1" aria-label="图纸长边格数" :disabled="busy" @change="clampEdge" /></div>
            <p class="bead-help">格子越多，细节越丰富，也需要更多豆子。</p>
            <label class="bead-field-label" for="bead-colors">最多使用几种颜色</label><select id="bead-colors" v-model.number="maxColors" aria-label="最多颜色数" :disabled="busy"><option v-for="count in [8, 16, 24]" :key="count" :value="count">{{ count }} 种{{ count === 8 ? ' · 简单图案' : count === 16 ? ' · 日常使用' : ' · 丰富细节' }}</option></select>
            <p class="bead-help">自动选色会控制在此数量内，手动改色可增加颜色。</p>
            <div class="bead-palette-note"><strong>Artkal S 系列配色</strong><p>采用官方色号。屏幕颜色供参考，请用同一系列的实物豆子核对。</p></div>
            <UiButton class="bead-generate" :disabled="!source || busy" :loading="generating" @click="generate()">{{ loading ? '正在读取图片' : generating ? '正在生成图纸' : '生成图纸' }}</UiButton>
            <p v-if="dimensions" class="bead-target">预计 {{ dimensions.width }} × {{ dimensions.height }} 格 · 透明区域留空</p>
          </section>
        </aside>
        <section class="bead-result" aria-label="图纸结果">
          <div ref="resultHeading" class="bead-result__top"><div><span class="bead-kicker">你的图纸</span><h2>{{ sourceName || '从一张图片开始' }}</h2></div><div v-if="pattern" class="bead-stats" aria-label="图纸统计" aria-live="polite"><span><strong>{{ pattern.width }} × {{ pattern.height }}</strong> 格</span><span><strong>{{ total.toLocaleString('zh-CN') }}</strong> 颗</span><span><strong>{{ counts.length }}</strong> 色</span></div></div>
          <p v-if="error" role="alert" class="bead-alert">{{ error }}</p>
          <p v-if="stale" class="bead-stale" role="status">图片或参数已调整，点击生成图纸更新结果。当前显示和导出仍为上一次图纸。</p>
          <div class="bead-viewbar"><div class="bead-tabs" role="group" aria-label="查看方式"><button type="button" :aria-pressed="view === 'preview'" @click="view = 'preview'">效果图</button><button type="button" :aria-pressed="view === 'chart'" @click="view = 'chart'">编号图纸</button><button type="button" :aria-pressed="view === 'original'" @click="view = 'original'">原图</button></div><label v-if="view !== 'original'" class="bead-zoom">缩放<select v-model.number="zoom" aria-label="图纸缩放"><option v-for="value in [100, 150, 200, 300]" :key="value" :value="value">{{ value }}%</option></select></label></div>
          <div ref="stage" class="bead-stage" :class="{ 'is-editing': tool !== 'inspect' }" aria-label="图纸工作区" :aria-busy="busy">
            <img v-if="view === 'original' && source" :src="source.url" alt="当前选择的原图" class="bead-original" />
            <canvas v-show="pattern && view !== 'original'" ref="canvas" role="img" aria-label="拼豆图案画布" aria-describedby="bead-canvas-help" tabindex="0" @pointerdown="beginStroke" @pointermove="moveStroke" @pointerup="finishStroke" @pointercancel="finishStroke" @lostpointercapture="finishStroke" @keydown="onCanvasKey" @focus="canvasFocused = true" @blur="canvasFocused = false" />
            <div v-if="!pattern" class="bead-empty"><PictureOutlined /><p>{{ busy ? '正在准备示例图纸…' : '选择图片，或使用示例体验' }}</p></div>
            <div v-if="busy && pattern" class="bead-busy" role="status">{{ loading ? '正在读取图片…' : '正在生成图纸…' }}</div>
          </div>
          <div class="bead-editor"><div class="bead-toolbuttons" role="group" aria-label="编辑工具"><button type="button" :aria-pressed="tool === 'inspect'" :disabled="!pattern || busy" @click="selectTool('inspect')">查看</button><button type="button" :aria-pressed="tool === 'paint'" :disabled="!pattern || busy" @click="selectTool('paint')">画笔</button><button type="button" :aria-pressed="tool === 'erase'" :disabled="!pattern || busy" @click="selectTool('erase')"><ScissorOutlined /> 橡皮</button><button type="button" :disabled="!history.length || busy" @click="undo"><UndoOutlined /> 撤销</button></div><label v-if="tool === 'paint'" class="bead-brush"><span :style="{ backgroundColor: selectedHex }"></span><select v-model="selectedColor" aria-label="画笔色号"><option v-for="color in palette" :key="color.code" :value="color.code">{{ color.code }}</option></select></label><span v-else class="bead-cursor">{{ cellDescription }}</span></div>
          <p id="bead-canvas-help" class="bead-help bead-canvas-help">{{ tool === 'inspect' ? '点击格子或下方色块，查看同色位置。画布可局部滚动。' : tool === 'paint' ? '选择色号后点按或拖动涂色，可撤销最近 30 次操作。' : '点按或拖动擦除，擦除后的格子不再计入用量。' }}<span>键盘：方向键移动，回车操作。</span></p>
          <div v-if="counts.length" class="bead-swatches" aria-label="图纸用色"><button v-for="item in counts" :key="item.color.code" type="button" :title="`${item.color.code} · ${item.count} 颗`" :aria-label="`突出 ${item.color.code}，${item.count} 颗`" :aria-pressed="highlight === item.color.code" @click="selectColor(item.color.code)"><span :style="{ backgroundColor: item.color.hex }"></span>{{ item.color.code }}</button><button v-if="highlight" type="button" class="bead-clear-highlight" @click="highlight = null">取消突出</button></div>
          <div class="bead-downloads"><UiButton :disabled="!pattern || busy || exporting" @click="exportResult('chart')"><DownloadOutlined /> 下载图纸</UiButton><UiButton tone="subtle" :disabled="!pattern || busy || exporting" @click="exportResult('preview')">下载效果图</UiButton><UiButton tone="ghost" :disabled="!pattern || busy || exporting" @click="exportResult('csv')">导出材料清单</UiButton><UiButton tone="ghost" :disabled="!pattern || busy || exporting" @click="exportResult('print')">打印 / 另存 PDF</UiButton></div>
          <details class="bead-materials"><summary>材料清单 <span>{{ counts.length }} 种颜色，共 {{ total.toLocaleString('zh-CN') }} 颗</span></summary><div class="bead-materials__scroll"><table aria-label="材料清单"><thead><tr><th>颜色</th><th>Artkal S 色号</th><th>所需颗数</th></tr></thead><tbody><tr v-for="item in counts" :key="item.color.code"><td><span class="bead-table-color" :style="{ backgroundColor: item.color.hex }"></span></td><td>{{ item.color.code }}</td><td>{{ item.count }}</td></tr></tbody><tfoot><tr><th colspan="2">合计（不含空格）</th><td>{{ total }}</td></tr></tfoot></table></div><p class="bead-help">用量以当前图纸为准，不额外计入备用豆。</p></details>
        </section>
      </div>
      <section class="bead-guide" aria-labelledby="bead-guide-title"><h2 id="bead-guide-title">第一次接触拼豆？</h2><div><p><strong>一格，一颗豆</strong>拼豆是把彩色小塑料珠排列成图案。编号图纸告诉你每个位置放哪一种颜色，空格表示不用放。</p><p><strong>从简单图案开始</strong>轮廓清楚、背景简单的图片更容易辨认。真人照片建议先裁近人物，再增加格数和颜色。</p><p><strong>按图纸准备材料</strong>材料清单写明 Artkal S 色号和数量。打印图用于对照坐标摆豆，未校准为拼板的等比例垫图。</p></div></section>
      <details class="bead-about"><summary>色卡、示例与开源说明</summary><p>色卡来自 <a href="https://www.artkalfusebeads.com/pages/s-color-chart" target="_blank" rel="noopener noreferrer">Artkal 官方 RGB 色卡</a>，不包含缺少 RGB 数据的金属色。屏幕、打印和实物颜色可能存在差异。</p><p>盆栽示例为本站手绘；人像示例为 NASA / Eileen Collins，由 scikit-image 提供，仅用于图像转换演示，不代表本人或 NASA 为本站背书。</p><p>颜色算法参考并局部复用 <a href="https://github.com/Jett-Wu/Perler_Beads_Generator" target="_blank" rel="noopener noreferrer">Jett-Wu / Perler Beads Generator</a>（MIT）。<a href="/tools/bead-pattern/OPEN_SOURCE.md" target="_blank">开源归属</a> · <a href="/tools/bead-pattern/SOURCES.md" target="_blank">素材来源</a></p></details>
    </main><footer class="bead-footer"><SiteNavigation /></footer>
  </div>
</template>

<style scoped lang="scss" src="./BeadPatternWorkspace.scss"></style>
