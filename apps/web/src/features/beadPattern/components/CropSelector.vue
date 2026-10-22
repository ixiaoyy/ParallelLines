<script setup lang="ts">
import { ref } from "vue";
import type { CropRegion } from "../model";

const props = defineProps<{ src: string; imageWidth: number; imageHeight: number; modelValue: CropRegion; disabled?: boolean }>();
const emit = defineEmits<{ "update:modelValue": [value: CropRegion] }>();
const frame = ref<HTMLElement | null>(null);
let start: { x: number; y: number } | null = null;
let before: CropRegion | null = null;

/** 将触点限制在图片实际边界内，返回与分辨率无关的比例坐标。 */
function point(event: PointerEvent) {
  const rect = frame.value!.getBoundingClientRect();
  return { x: Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width)), y: Math.min(1, Math.max(0, (event.clientY - rect.top) / rect.height)) };
}

/** 拖动重新框选取景；轻点不改变已有区域。 */
function begin(event: PointerEvent) {
  if (props.disabled || event.button !== 0) return;
  start = point(event);
  before = { ...props.modelValue };
  frame.value?.setPointerCapture(event.pointerId);
}
/** 根据当前触点更新非零选区，避免轻点生成不可用的小区域。 */
function move(event: PointerEvent) {
  if (!start) return;
  const end = point(event);
  const width = Math.abs(end.x - start.x);
  const height = Math.abs(end.y - start.y);
  if (width < 0.02 || height < 0.02) return;
  emit("update:modelValue", { x: Math.min(start.x, end.x), y: Math.min(start.y, end.y), width, height });
}
/** 结束取景拖动；系统取消时恢复拖动前区域。 */
function finish(event: PointerEvent) {
  if (!start) return;
  if (event.type === "pointercancel" && before) emit("update:modelValue", before);
  start = null;
  before = null;
  if (frame.value?.hasPointerCapture(event.pointerId)) frame.value.releasePointerCapture(event.pointerId);
}
/** 恢复完整原图，不改变源文件。 */
function fullImage() { emit("update:modelValue", { x: 0, y: 0, width: 1, height: 1 }); }
/** 生成原图中心的最大正方形取景，纵横坐标均为比例。 */
function square() {
  const size = Math.min(props.imageWidth, props.imageHeight);
  const width = size / props.imageWidth;
  const height = size / props.imageHeight;
  emit("update:modelValue", { x: (1 - width) / 2, y: (1 - height) / 2, width, height });
}

/** 百分比输入提供键盘取景方式，并保证选区始终落在原图内。 */
function setPart(key: keyof CropRegion, event: Event) {
  const value = Number((event.target as HTMLInputElement).value) / 100;
  const next = { ...props.modelValue };
  if (!Number.isFinite(value)) return;
  if (key === "x") next.x = Math.min(1 - next.width, Math.max(0, value));
  if (key === "y") next.y = Math.min(1 - next.height, Math.max(0, value));
  if (key === "width") next.width = Math.min(1 - next.x, Math.max(0.02, value));
  if (key === "height") next.height = Math.min(1 - next.y, Math.max(0.02, value));
  emit("update:modelValue", next);
}
</script>

<template>
  <div class="bead-crop">
    <div ref="frame" class="bead-crop__frame" :class="{ 'is-disabled': disabled }" @pointerdown="begin" @pointermove="move" @pointerup="finish" @pointercancel="finish" @lostpointercapture="finish">
      <img :src="src" alt="原图与当前取景范围" draggable="false" />
      <div class="bead-crop__selection" :style="{ left: `${modelValue.x * 100}%`, top: `${modelValue.y * 100}%`, width: `${modelValue.width * 100}%`, height: `${modelValue.height * 100}%` }"><span></span></div>
    </div>
    <p class="bead-help">拖动框选要保留的区域，让主体更突出。</p>
    <div class="bead-crop__actions"><button type="button" :disabled="disabled" @click="fullImage">保留整图</button><button type="button" :disabled="disabled" @click="square">居中正方形</button></div>
    <details class="bead-crop__precise">
      <summary>精确调整取景</summary>
      <div>
        <label v-for="item in [{ key: 'x' as const, label: '左边距' }, { key: 'y' as const, label: '上边距' }, { key: 'width' as const, label: '宽度' }, { key: 'height' as const, label: '高度' }]" :key="item.key">
          {{ item.label }} %<input type="number" :aria-label="`取景${item.label}百分比`" :value="Math.round(modelValue[item.key] * 100)" min="0" max="100" :disabled="disabled" @change="setPart(item.key, $event)" />
        </label>
      </div>
    </details>
  </div>
</template>
