<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import { ArrowLeftOutlined, PauseOutlined, ReloadOutlined } from "@ant-design/icons-vue";
import UiButton from "@/shared/ui/Button.vue";
import { advanceDunk, COURT, createDunkState, flapDunk, toggleDunkPause, type DunkState, type LossReason } from "./rules";
import { drawDunkCourt } from "./render";
import { readDunkBest, saveDunkBest } from "./storage";

const canvas = ref<HTMLCanvasElement | null>(null);
const surface = ref<HTMLDivElement | null>(null);
const phase = ref<DunkState["phase"]>("ready");
const score = ref(0);
const streak = ref(0);
const best = ref(0);
const loss = ref<LossReason>(null);
const showRules = ref(false);
let state = createDunkState();
let frame = 0;
let previousTime = 0;
let resizeObserver: ResizeObserver | undefined;
let context: CanvasRenderingContext2D | null = null;

const lossMessage = computed(() => {
  switch (loss.value) {
    case "ceiling": return "飞得太高，碰到天花板了";
    case "floor": return "球落地了，再试一次吧";
    case "wrong-way": return "要从篮圈上方落进去哦";
    case "missed": return "错过篮圈了，再试一次吧";
    default: return "找准节奏，再来一局";
  }
});

/** 同步少量可见状态；物理对象保留在本组件内，不触发每个坐标的 Vue 响应式更新。 */
function syncUi(): void {
  phase.value = state.phase;
  score.value = state.score;
  streak.value = state.streak;
  loss.value = state.loss;
  // 仅刷新纪录时写入本地存储，避免逐帧同步和重复诊断。
  if (state.score > best.value) best.value = saveDunkBest(state.score);
}

/** 绘制当前逻辑状态；无可用画布上下文时不启动物理循环。 */
function paint(): void {
  if (context) drawDunkCourt(context, state);
}

/** 停止动画并清空时间基线；恢复、重开和标签页切换都不会补算旧帧。 */
function stopFrame(): void {
  cancelAnimationFrame(frame);
  frame = 0;
  previousTime = 0;
}

/** 请求下一帧，每次最多处理 0.2 秒，物理由规则模块进一步细分以防穿透。 */
function tick(time: number): void {
  frame = 0;
  if (state.phase !== "running" || !context) return;
  const elapsed = previousTime === 0 ? 0 : (time - previousTime) / 1000;
  previousTime = time;
  state = advanceDunk(state, elapsed);
  syncUi();
  paint();
  if (state.phase === "running") frame = requestAnimationFrame(tick);
  else stopFrame();
}

/** 点按球场和空格共用入口；暂停及结束由明确按钮恢复，避免误触重开。 */
function flap(): void {
  if (document.hidden || !context) return;
  state = flapDunk(state);
  syncUi();
  paint();
  canvas.value?.focus({ preventScroll: true });
  if (state.phase === "running" && frame === 0) frame = requestAnimationFrame(tick);
}

/** 单指、主键点按球场给予上跳；避免拖动、多指和鼠标右键产生额外输入。 */
function onPointer(event: PointerEvent): void {
  if (!event.isPrimary || event.button !== 0) return;
  event.preventDefault();
  canvas.value?.focus({ preventScroll: true });
  flap();
}

/** 暂停或继续当前局；恢复必须由用户动作触发，不自动恢复隐藏前的输入。 */
function togglePause(): void {
  state = toggleDunkPause(state);
  stopFrame();
  syncUi();
  paint();
  canvas.value?.focus({ preventScroll: true });
  if (state.phase === "running" && !document.hidden) frame = requestAnimationFrame(tick);
}

/** 重建开局并保留最高分，回到准备画面等待首次点按。 */
function restart(): void {
  stopFrame();
  state = createDunkState();
  syncUi();
  paint();
  canvas.value?.focus({ preventScroll: true });
}

/** 仅在游戏区域处理空格与暂停键，保留链接、按钮和其他页面控件的键盘行为。 */
function onKeydown(event: KeyboardEvent): void {
  const target = event.target;
  if (target instanceof HTMLElement && target.closest("button, a, input, textarea, select")) return;
  if (event.code === "Space" && !event.repeat) {
    event.preventDefault();
    flap();
  } else if ((event.code === "KeyP" || event.code === "Escape") && !event.repeat &&
    (state.phase === "running" || state.phase === "paused")) {
    event.preventDefault();
    togglePause();
  }
}

/** 按显示宽度和有限 DPR 更新画布，横竖屏变化不会重置物理位置。 */
function resizeCanvas(): void {
  if (!canvas.value || !surface.value || !context) return;
  const width = surface.value.getBoundingClientRect().width;
  if (width <= 0) return;
  const ratio = Math.min(window.devicePixelRatio || 1, 2);
  canvas.value.width = Math.round(width * ratio);
  canvas.value.height = Math.round(width * COURT.height / COURT.width * ratio);
  context.setTransform(canvas.value.width / COURT.width, 0, 0, canvas.value.height / COURT.height, 0, 0);
  paint();
}

/** 标签页隐藏或窗口失焦自动暂停，回到页面后由玩家自行继续。 */
function autoPause(): void {
  if (state.phase !== "running") return;
  state = toggleDunkPause(state);
  stopFrame();
  syncUi();
  paint();
}

/** 只在真正隐藏时暂停，显示事件不自动改变游戏状态。 */
function onVisibility(): void {
  if (document.hidden) autoPause();
}

onMounted(() => {
  best.value = readDunkBest();
  context = canvas.value?.getContext("2d") ?? null;
  resizeCanvas();
  if (surface.value) {
    resizeObserver = new ResizeObserver(resizeCanvas);
    resizeObserver.observe(surface.value);
  }
  window.addEventListener("resize", resizeCanvas);
  window.addEventListener("blur", autoPause);
  document.addEventListener("visibilitychange", onVisibility);
});

onBeforeUnmount(() => {
  // 页面离开时一并清理循环、观察器和全局事件，不保留后台游戏任务。
  stopFrame();
  resizeObserver?.disconnect();
  window.removeEventListener("resize", resizeCanvas);
  window.removeEventListener("blur", autoPause);
  document.removeEventListener("visibilitychange", onVisibility);
  context = null;
});
</script>

<template>
  <main class="flappy-dunk" @keydown="onKeydown">
    <div class="flappy-dunk__layout">
      <aside class="flappy-dunk__intro">
        <RouterLink to="/" class="flappy-dunk__back"><ArrowLeftOutlined aria-hidden="true" /> 返回目录</RouterLink>
        <p class="flappy-dunk__eyebrow">一颗篮球，一双小翅膀</p>
        <h1 aria-label="飞翼灌篮">飞翼<span>灌篮</span></h1>
        <p class="flappy-dunk__description">轻轻一点，让篮球飞起来。<br />找准节奏，从上方落进篮圈。</p>
        <div id="dunk-rules" class="flappy-dunk__rule-detail" :class="{ 'flappy-dunk__rule-detail--open': showRules }">
          <ol class="flappy-dunk__rules">
            <li><span>01</span> 点按球场或按空格，向上飞</li>
            <li><span>02</span> 从上往下穿圈，才算进球</li>
            <li><span>03</span> 连续空心入圈，最多每圈 5 分</li>
          </ol>
          <p class="flappy-dunk__note">避开天花板和地板，别漏掉篮圈。</p>
        </div>
        <div class="flappy-dunk__actions">
          <UiButton class="flappy-dunk__rules-toggle" tone="ghost" :aria-expanded="showRules" aria-controls="dunk-rules" @click="showRules = !showRules">{{ showRules ? '收起玩法' : '查看玩法' }}</UiButton>
          <UiButton v-if="phase === 'running' || phase === 'paused'" tone="subtle" @click="togglePause">
            <PauseOutlined aria-hidden="true" />{{ phase === 'paused' ? '继续游戏' : '暂停' }}
          </UiButton>
          <UiButton tone="ghost" @click="restart"><ReloadOutlined aria-hidden="true" />重新开始</UiButton>
        </div>
        <p class="flappy-dunk__local-record">最高分保存在当前浏览器 · <a href="/licenses/arcade-games.txt" target="_blank" rel="noopener noreferrer">开源许可</a></p>
      </aside>

      <section class="flappy-dunk__game" aria-label="飞翼灌篮球场">
        <div class="flappy-dunk__scoreboard">
          <div><span>本局得分</span><strong data-testid="dunk-score">{{ score }}</strong></div>
          <div><span>最高纪录</span><strong>{{ best }}</strong></div>
          <div class="flappy-dunk__streak"><span>空心连击</span><strong>{{ streak }}<small> 连</small></strong></div>
        </div>
        <div ref="surface" class="flappy-dunk__surface" :data-phase="phase">
          <canvas ref="canvas" tabindex="0" aria-label="点按或按空格使篮球向上跳，P 键暂停" @pointerdown="onPointer">
            点按或按空格使篮球向上跳，从上往下穿过篮圈得分。
          </canvas>
          <div v-if="phase !== 'running'" class="flappy-dunk__overlay" :class="{ 'flappy-dunk__overlay--ready': phase === 'ready' }">
            <div class="flappy-dunk__dialog" role="status" aria-live="polite">
              <template v-if="phase === 'ready'">
                <span class="flappy-dunk__dialog-label">准备起飞</span>
                <h2>把下一球投进去</h2>
                <p>点击开始，也可以按空格</p>
                <UiButton data-testid="dunk-start" @click="flap">开始游戏</UiButton>
              </template>
              <template v-else-if="phase === 'paused'">
                <span class="flappy-dunk__dialog-label">稍息一下</span>
                <h2>游戏已暂停</h2>
                <p>你的分数和球场都留在这里</p>
                <UiButton @click="togglePause">继续游戏</UiButton>
              </template>
              <template v-else>
                <span class="flappy-dunk__dialog-label">这一局，拿下 {{ score }} 分</span>
                <h2>{{ lossMessage }}</h2>
                <p>{{ score > 0 && score === best ? '新的好成绩！继续挑战自己吧' : '轻点起跳，松手落进篮圈' }}</p>
                <UiButton data-testid="dunk-restart" @click="restart">再来一局</UiButton>
              </template>
            </div>
          </div>
        </div>
        <p class="flappy-dunk__court-caption">点按 / 空格起跳 <span>·</span> P 暂停</p>
      </section>
    </div>
  </main>
</template>

<style scoped lang="scss" src="./FlappyDunkGame.scss"></style>
