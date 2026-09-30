<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import UiButton from "@/shared/ui/Button.vue";
import {
  DIRECTION_DELTA, LEVEL_COUNT, createGame, elapseTime, setPlaying, snakeDirection,
  takeHint, tapSnake, type Cell, type Snake,
} from "./rules";
import { loadProgress, saveProgress, unlockNext } from "./storage";

interface Motion { snake: Snake; kind: "escape" | "bump"; progress: number; duration: number }
interface SnakeColor { name: string; base: string; dark: string; light: string }
const colors: SnakeColor[] = [
  { name: "蓝色", base: "#5a9dee", dark: "#3278c8", light: "#93c9ff" },
  { name: "橘色", base: "#f8ad3f", dark: "#d98322", light: "#ffd386" },
  { name: "紫色", base: "#b982e8", dark: "#9860c7", light: "#dcacff" },
  { name: "绿色", base: "#8ec65e", dark: "#62a13a", light: "#c3e997" },
  { name: "粉色", base: "#ed889d", dark: "#c95b75", light: "#ffc0cf" },
  { name: "青色", base: "#69c9d5", dark: "#3aa5b4", light: "#a5edf2" },
];
const arrows = { up: "↑", right: "→", down: "↓", left: "←" };
const directionNames = { up: "上", right: "右", down: "下", left: "左" };
const directionAngles = { up: -90, right: 0, down: 90, left: 180 };
const progress = ref(loadProgress());
const state = ref(createGame(progress.value.highestUnlocked));
const motion = ref<Motion | null>(null);
const zoom = ref(100);
const notice = ref("先看蛇头朝向，再找一条畅通的路。");
const board = ref<HTMLDivElement | null>(null);
const reduceMotion = ref(false);
let frame: number | null = null;
let lastFrame = 0;
let clockPendingMs = 0;
let motionQuery: MediaQueryList | null = null;

// 按初始蛇头位置排列显示与键盘选择，避免关卡存储顺序泄露解题顺序；离场后颜色保持不变。
const spatialOrder = computed(() => new Map([...state.value.level.snakes].sort((left, right) => {
  const a = left.path[left.path.length - 1];
  const b = right.path[right.path.length - 1];
  return a.y - b.y || a.x - b.x;
}).map((snake, index) => [snake.id, index])));
const activeSnakes = computed(() => state.value.snakes.filter((snake) => snake.active)
  .sort((left, right) => spatialOrder.value.get(left.id)! - spatialOrder.value.get(right.id)!));
const visibleSnakes = computed(() => motion.value?.kind === "escape"
  ? [...activeSnakes.value, motion.value.snake] : activeSnakes.value);
const gridSize = computed(() => state.value.level.gridSize);
const viewBox = computed(() => `-1.1 -1.1 ${gridSize.value + 2.2} ${gridSize.value + 2.2}`);
const clockLabel = computed(() => {
  const seconds = Math.ceil(state.value.remainingMs / 1_000);
  return `${Math.floor(seconds / 60).toString().padStart(2, "0")}:${(seconds % 60).toString().padStart(2, "0")}`;
});
const escapedCount = computed(() => state.value.snakes.length - activeSnakes.value.length);
const selectedLevels = computed(() => Array.from({ length: progress.value.highestUnlocked }, (_, index) => index + 1));
const blocked = computed(() => state.value.status !== "playing" || motion.value !== null);
const showCurtain = computed(() => state.value.status !== "playing" && !(state.value.status === "won" && motion.value));
const tier = computed(() => state.value.level.number <= 5 ? "初入花园" : state.value.level.number <= 15 ? "弯弯小径"
  : state.value.level.number <= 30 ? "缤纷迷宫" : "花园高手");

/** 按初始蛇头位置分配配色索引，离场动画仍使用原配色。 */
function colorIndex(snake: Snake): number {
  return spatialOrder.value.get(snake.id)! % colors.length;
}

/** 获取位置对应配色，动画期间保留原关卡的颜色身份。 */
function colorFor(snake: Snake): SnakeColor {
  return colors[colorIndex(snake)];
}

/** 沿身体原路径前进，再沿头方向延伸，弯曲身体不会横扫旁边的小蛇。 */
function pathFor(snake: Snake): Cell[] {
  const moving = motion.value;
  if (!moving || moving.snake.id !== snake.id || moving.kind !== "escape") return snake.path;
  const head = snake.path[snake.path.length - 1];
  const delta = DIRECTION_DELTA[snakeDirection(snake)];
  const offset = moving.progress * (snake.path.length + gridSize.value + 2);
  const pointAt = (index: number): Cell => index < snake.path.length ? snake.path[index]
    : { x: head.x + delta.x * (index - snake.path.length + 1), y: head.y + delta.y * (index - snake.path.length + 1) };
  return snake.path.map((_, index) => {
    const from = pointAt(index + Math.floor(offset));
    const to = pointAt(index + Math.floor(offset) + 1);
    const fraction = offset % 1;
    return { x: from.x + (to.x - from.x) * fraction, y: from.y + (to.y - from.y) * fraction };
  });
}

/** 将格子中心转为 SVG 折线，保留分节小蛇的圆角连接。 */
function polyline(snake: Snake): string {
  return pathFor(snake).map((cell) => `${cell.x + 0.5},${cell.y + 0.5}`).join(" ");
}

/** 蛇头表情始终面向前进方向；撞退只在本条蛇上短暂位移。 */
function headTransform(snake: Snake): string {
  const path = pathFor(snake);
  const head = path[path.length - 1];
  return `translate(${head.x + 0.5} ${head.y + 0.5}) rotate(${directionAngles[snakeDirection(snake)]})`;
}

/** 撞击后原位退回，移动量小于一格，避免表现为穿过其他蛇。 */
function bumpTransform(snake: Snake): string {
  if (motion.value?.snake.id !== snake.id || motion.value.kind !== "bump") return "";
  const delta = DIRECTION_DELTA[snakeDirection(snake)];
  const displacement = Math.sin(motion.value.progress * Math.PI * 2) * 0.16;
  return `translate(${delta.x * displacement} ${delta.y * displacement})`;
}

/** 设置 44 像素蛇头触点，棋盘缩放时仍使用真实格子位置。 */
function headButtonStyle(snake: Snake): Record<string, string> {
  const head = snake.path[snake.path.length - 1];
  const extent = gridSize.value + 2.2;
  return { left: `${(head.x + 1.6) / extent * 100}%`, top: `${(head.y + 1.6) / extent * 100}%` };
}

/** 用从一开始的行列描述蛇头位置，区分同色小蛇而不公开解题编号。 */
function headPosition(snake: Snake): string {
  const head = snake.path[snake.path.length - 1];
  return `第${head.y + 1}行第${head.x + 1}列`;
}

/** 给键盘和辅助技术提供颜色、蛇头位置及方向，不提前公开是否可离场。 */
function snakeLabel(snake: Snake): string {
  return `${colorFor(snake).name}小蛇，蛇头在${headPosition(snake)}，朝${directionNames[snakeDirection(snake)]}`;
}

/** 清除动画帧和时间基准，暂停及离开页面均不留下后台计时器。 */
function stopClock(): void {
  if (frame !== null) window.cancelAnimationFrame(frame);
  frame = null;
  lastFrame = 0;
  clockPendingMs = 0;
}

/** 每帧只推进当前动画，计时以真实经过时间累计，避免掉帧让时间变慢。 */
function advanceFrame(timestamp: number): void {
  frame = null;
  const delta = lastFrame === 0 ? 0 : Math.max(0, timestamp - lastFrame);
  lastFrame = timestamp;
  if (state.value.status === "playing") {
    clockPendingMs += delta;
    // 计时画面每 100 毫秒更新，避免整块棋盘每帧重复渲染。
    if (clockPendingMs >= 100) {
      state.value = elapseTime(state.value, clockPendingMs);
      clockPendingMs = 0;
    }
  }
  if (motion.value && (state.value.status === "playing" || state.value.status === "won")) {
    const next = motion.value.progress + delta / motion.value.duration;
    motion.value = next >= 1 ? null : { ...motion.value, progress: next };
    if (next >= 1) void nextTick(focusNextSnake);
  }
  if (state.value.status === "lost") motion.value = null;
  if (state.value.status === "playing" || (state.value.status === "won" && motion.value)) frame = window.requestAnimationFrame(advanceFrame);
  else lastFrame = 0;
}

/** 在开始和继续时安排唯一动画循环，不重复注册 RAF。 */
function beginClock(): void {
  if (frame !== null) return;
  lastFrame = performance.now();
  frame = window.requestAnimationFrame(advanceFrame);
}

/** 开始或继续当前关卡，已结束的关卡必须通过重开按钮重置。 */
function beginGame(): void {
  state.value = setPlaying(state.value, true);
  if (state.value.status === "playing") beginClock();
  void nextTick(focusNextSnake);
}

/** 暂停前补齐最后一帧到当前时刻的用时，页面隐藏时同样执行。 */
function pauseGame(): void {
  if (state.value.status !== "playing") return;
  if (lastFrame > 0) state.value = elapseTime(state.value, clockPendingMs + performance.now() - lastFrame);
  state.value = setPlaying(state.value, false);
  stopClock();
}

/** 重开或进入已解锁关卡时清理旧动画，避免旧回调修改新关卡。 */
function loadLevel(number: number, playing = false): void {
  stopClock();
  motion.value = null;
  state.value = createGame(Math.min(number, progress.value.highestUnlocked));
  zoom.value = 100;
  notice.value = "先看蛇头朝向，再找一条畅通的路。";
  if (playing) beginGame();
}

/** 点击后立即提交规则状态，短暂锁定输入，快速连点不会重复扣命。 */
function chooseSnake(snake: Snake): void {
  if (blocked.value) return;
  const result = tapSnake(state.value, snake.id);
  if (result.outcome === "ignored") return;
  state.value = result.state;
  if (result.outcome === "blocked") notice.value = `前方有小蛇挡路，剩余 ${state.value.lives} 条生命。`;
  else notice.value = "小蛇出洞啦！";
  // 动画只影响显示，生命、胜负与通关解锁均由纯规则结果决定。
  motion.value = reduceMotion.value || state.value.status === "lost" ? null
    : { snake, kind: result.outcome === "escaped" ? "escape" : "bump", progress: 0, duration: result.outcome === "escaped" ? 650 : 320 };
  if (state.value.status === "won") {
    progress.value = unlockNext(progress.value, state.value.level.number);
    saveProgress(progress.value);
    notice.value = "所有小蛇都顺利回家啦。";
  }
  if (motion.value) beginClock();
  else void nextTick(focusNextSnake);
}

/** 身体也可点按；用 SVG 实际坐标找占用格子，缩放和滚动不改变判断。 */
function handleBoardPointer(event: MouseEvent): void {
  if (blocked.value || event.button !== 0) return;
  const svg = board.value?.querySelector<SVGSVGElement>(".se-board__svg");
  const matrix = svg?.getScreenCTM();
  if (!matrix) return;
  const point = new DOMPoint(event.clientX, event.clientY).matrixTransform(matrix.inverse());
  const x = Math.floor(point.x);
  const y = Math.floor(point.y);
  const snake = activeSnakes.value.find((candidate) => candidate.path.some((cell) => cell.x === x && cell.y === y));
  if (snake) chooseSnake(snake);
}

/** 密集关卡的大触点可能重叠；指针按实际格子命中，键盘按聚焦按钮身份操作。 */
function handleHeadClick(snake: Snake, event: MouseEvent): void {
  if (event.detail === 0) chooseSnake(snake);
  else handleBoardPointer(event);
}

/** 提示高亮一条当前可离场的小蛇，三次用完后不会自动替玩家操作。 */
function showHint(): void {
  if (blocked.value) return;
  state.value = takeHint(state.value);
  const snake = activeSnakes.value.find((candidate) => candidate.id === state.value.hintId);
  if (snake) notice.value = "已圈出一条前方畅通的小蛇。";
}

/** 键盘按方向键在蛇头按钮间循环，回车或空格由原生按钮执行。 */
function handleSnakeKey(event: KeyboardEvent): void {
  if (!["ArrowUp", "ArrowRight", "ArrowDown", "ArrowLeft"].includes(event.key)) return;
  event.preventDefault();
  const buttons = [...(board.value?.querySelectorAll<HTMLButtonElement>(".se-head-button:not(:disabled)") ?? [])];
  const current = buttons.indexOf(event.currentTarget as HTMLButtonElement);
  const delta = event.key === "ArrowRight" || event.key === "ArrowDown" ? 1 : -1;
  buttons[(current + delta + buttons.length) % buttons.length]?.focus();
}

/** 仅当原蛇头按钮被移除、焦点掉到文档时补回，避免抢走工具按钮焦点。 */
function focusNextSnake(): void {
  if (state.value.status !== "playing") return;
  if (document.activeElement === document.body || document.activeElement === null) {
    board.value?.querySelector<HTMLButtonElement>(".se-head-button:not(:disabled)")?.focus({ preventScroll: true });
  }
}

/** 选择关卡只接受已解锁的选项，不从 DOM 输入绕过进度。 */
function changeLevel(event: Event): void {
  const number = Number((event.target as HTMLSelectElement).value);
  if (Number.isInteger(number) && number >= 1 && number <= progress.value.highestUnlocked) loadLevel(number);
}

/** 页面进入后台自动暂停，回到页面后由玩家主动继续。 */
function handleVisibility(): void {
  if (document.hidden) pauseGame();
}

/** 用户减少动画时立即收掉显示动画，规则状态与计时均不回退。 */
function handleMotionPreference(): void {
  reduceMotion.value = motionQuery?.matches ?? false;
  if (reduceMotion.value) motion.value = null;
}

onMounted(() => {
  motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
  handleMotionPreference();
  motionQuery.addEventListener("change", handleMotionPreference);
  document.addEventListener("visibilitychange", handleVisibility);
});
onBeforeUnmount(() => {
  stopClock();
  motionQuery?.removeEventListener("change", handleMotionPreference);
  document.removeEventListener("visibilitychange", handleVisibility);
});
</script>

<template>
  <main class="se-game" :data-status="state.status">
    <header class="se-game__heading">
      <div>
        <span class="se-game__eyebrow"><i aria-hidden="true"></i>花园解围计划</span>
        <h1>蛇蛇出洞<span aria-hidden="true">✿</span></h1>
        <p>看准蛇头方向，帮缠在一起的小蛇找到出口。</p>
      </div>
      <RouterLink to="/" class="se-game__back">返回目录 <span aria-hidden="true">↗</span></RouterLink>
    </header>

    <div class="se-game__layout">
      <section class="se-arena" aria-label="蛇蛇出洞游戏区">
        <div class="se-hud">
          <div class="se-hud__level"><small>{{ tier }}</small><strong>第 {{ state.level.number }} 关</strong></div>
          <div class="se-hud__lives" :aria-label="`剩余 ${state.lives} 条生命`"><span v-for="heart in 3" :key="heart" :class="{ 'is-empty': heart > state.lives }" aria-hidden="true">♥</span></div>
          <div class="se-hud__clock" :class="{ 'is-urgent': state.remainingMs < 30_000 }" aria-label="剩余时间"><span aria-hidden="true">◷</span>{{ clockLabel }}</div>
        </div>

        <div class="se-garden">
          <div class="se-garden__plants" aria-hidden="true"><span>✿</span><span>✿</span><span>✿</span><span>✿</span><span>✿</span></div>
          <div class="se-board-scroll">
            <div ref="board" class="se-board" :style="{ width: `${zoom}%` }">
              <svg class="se-board__svg" :viewBox="viewBox" aria-hidden="true" @pointerup="handleBoardPointer">
                <defs>
                  <pattern id="se-grid" width="1" height="1" patternUnits="userSpaceOnUse"><circle cx="0.5" cy="0.5" r="0.035" fill="#d9c5a8" /></pattern>
                  <linearGradient v-for="(color, index) in colors" :id="`se-color-${index}`" :key="color.name" x1="0" y1="0" x2="0.9" y2="1"><stop offset="0" :stop-color="color.light" /><stop offset="0.5" :stop-color="color.base" /><stop offset="1" :stop-color="color.dark" /></linearGradient>
                  <filter id="se-snake-shadow" x="-20%" y="-20%" width="140%" height="150%"><feDropShadow dx="0" dy="0.065" stdDeviation="0.025" flood-color="#8e613d" flood-opacity="0.25" /></filter>
                </defs>
                <rect :width="gridSize" :height="gridSize" rx="0.5" fill="url(#se-grid)" />
                <g v-for="snake in visibleSnakes" :key="snake.id" class="se-snake" :class="{ 'se-snake--hint': state.hintId === snake.id }" :transform="bumpTransform(snake)" filter="url(#se-snake-shadow)">
                  <polyline v-if="state.hintId === snake.id" :points="polyline(snake)" fill="none" stroke="#fff7bd" stroke-width="1.02" stroke-linecap="round" stroke-linejoin="round" />
                  <polyline :points="polyline(snake)" fill="none" :stroke="colorFor(snake).dark" stroke-width="0.73" stroke-linecap="round" stroke-linejoin="round" />
                  <circle v-for="(cell, index) in pathFor(snake)" :key="index" :cx="cell.x + 0.5" :cy="cell.y + 0.5" :r="index === 0 ? 0.29 : 0.4" :fill="`url(#se-color-${colorIndex(snake)})`" :stroke="colorFor(snake).dark" stroke-width="0.035" />
                  <g :transform="headTransform(snake)">
                    <ellipse cx="0.04" cy="0" rx="0.47" ry="0.43" :fill="`url(#se-color-${colorIndex(snake)})`" :stroke="colorFor(snake).dark" stroke-width="0.035" />
                    <ellipse cx="0.14" cy="-0.18" rx="0.17" ry="0.14" fill="#fff" /><ellipse cx="0.14" cy="0.18" rx="0.17" ry="0.14" fill="#fff" />
                    <circle cx="0.19" cy="-0.17" r="0.074" fill="#28334c" /><circle cx="0.19" cy="0.17" r="0.074" fill="#28334c" />
                    <circle cx="0.215" cy="-0.195" r="0.023" fill="#fff" /><circle cx="0.215" cy="0.145" r="0.023" fill="#fff" />
                    <path d="M.31 -.03 Q.39 0 .31 .03" fill="none" stroke="#60464c" stroke-width="0.034" stroke-linecap="round" />
                  </g>
                </g>
              </svg>
              <button v-for="snake in activeSnakes" :key="snake.id" type="button" class="se-head-button" :class="{ 'se-head-button--hint': state.hintId === snake.id }" :style="headButtonStyle(snake)" :disabled="blocked" :aria-label="snakeLabel(snake)" @click="handleHeadClick(snake, $event)" @keydown="handleSnakeKey"></button>
            </div>
          </div>
          <div class="se-garden__edge" aria-hidden="true"><span class="se-watermelon"></span><span>回家的路，就在前方</span><span class="se-watermelon"></span></div>
          <div v-if="showCurtain" class="se-curtain">
            <div class="se-curtain__card" role="status">
              <span class="se-curtain__flower" aria-hidden="true">{{ state.status === 'won' ? '✿' : state.status === 'lost' ? '☁' : '☘' }}</span>
              <template v-if="state.status === 'ready'"><small>第 {{ state.level.number }} 关 · {{ tier }}</small><h2>小蛇们等你帮忙</h2><p>点击小蛇，沿着蛇头方向出洞。<br />遇到挡路的小蛇，先让它离开。</p><UiButton tone="primary" @click="beginGame">开始游戏 <span aria-hidden="true">→</span></UiButton></template>
              <template v-else-if="state.status === 'paused'"><small>休息一下</small><h2>花园暂停营业</h2><p>小蛇和时间都在原地等你。</p><UiButton tone="primary" @click="beginGame">继续游戏</UiButton></template>
              <template v-else-if="state.status === 'won'"><small>第 {{ state.level.number }} 关完成</small><h2>全部顺利出洞！</h2><p>{{ state.level.number === LEVEL_COUNT ? '你已走遍花园的每一条小径。' : '下一片花园，还有新的小蛇等你。' }}</p><UiButton v-if="state.level.number < LEVEL_COUNT" tone="primary" @click="loadLevel(state.level.number + 1, true)">下一关 <span aria-hidden="true">→</span></UiButton><UiButton v-else tone="primary" @click="loadLevel(1, true)">再游花园</UiButton><button class="se-curtain__secondary" type="button" @click="loadLevel(state.level.number, true)">再玩这关</button></template>
              <template v-else><small>这次先休息一下</small><h2>{{ state.failure === 'time' ? '时间到啦' : '生命用完啦' }}</h2><p>记住挡路的小蛇，再换一个顺序试试。</p><UiButton tone="primary" @click="loadLevel(state.level.number, true)">重新挑战</UiButton></template>
            </div>
          </div>
        </div>

        <div class="se-arena__progress"><span>{{ escapedCount }} / {{ state.snakes.length }} 条已出洞</span><div role="progressbar" :aria-valuenow="escapedCount" :aria-valuemin="0" :aria-valuemax="state.snakes.length" aria-label="离场进度"><i :style="{ width: `${escapedCount / state.snakes.length * 100}%` }"></i></div></div>
        <p class="se-arena__notice" role="status" aria-live="polite">{{ notice }}</p>
        <div class="se-tools">
          <button type="button" :disabled="blocked || state.hints === 0" @click="showHint"><span aria-hidden="true">☀</span>提示 <small>{{ state.hints }}</small></button>
          <button type="button" :disabled="state.status !== 'playing'" @click="pauseGame"><span aria-hidden="true">Ⅱ</span>暂停</button>
          <button type="button" @click="loadLevel(state.level.number, true)"><span aria-hidden="true">↻</span>重开</button>
          <label class="se-tools__zoom"><span>缩放</span><input v-model.number="zoom" type="range" min="100" max="180" step="10" aria-label="棋盘缩放" /><output>{{ zoom }}%</output></label>
        </div>
        <details class="se-snake-picker"><summary>按位置选择小蛇</summary><div><button v-for="snake in activeSnakes" :key="snake.id" type="button" :disabled="blocked" :class="{ 'is-hinted': state.hintId === snake.id }" :aria-label="snakeLabel(snake)" @click="chooseSnake(snake)"><i :style="{ background: colorFor(snake).base }" aria-hidden="true"></i>{{ headPosition(snake) }} <span aria-hidden="true">{{ arrows[snakeDirection(snake)] }}</span></button></div></details>
      </section>

      <aside class="se-guide">
        <div class="se-guide__title"><span aria-hidden="true">✿</span><div><small>花园小贴士</small><h2>顺着方向，慢慢来</h2></div></div>
        <ol><li><b>01</b><div><strong>认准蛇头</strong><p>小蛇只会朝蛇头方向走，点击身体也可以。</p></div></li><li><b>02</b><div><strong>先给朋友让路</strong><p>前方有其他小蛇会撞退，并扣一条生命。</p></div></li><li><b>03</b><div><strong>全部出洞就过关</strong><p>每关 3 条生命、3 次提示，限时 5 分钟。</p></div></li></ol>
        <div class="se-guide__levels"><label for="se-level-select">去过的花园</label><select id="se-level-select" :value="state.level.number" @change="changeLevel"><option v-for="number in selectedLevels" :key="number" :value="number">第 {{ number }} 关</option></select><p>已解锁 {{ progress.highestUnlocked }} / {{ LEVEL_COUNT }} 关</p></div>
        <p class="se-guide__keyboard">键盘也能玩：Tab 选择，方向键切换小蛇，空格或回车出洞。</p>
        <p class="se-guide__credit">玩法规则与关卡基于 <a href="https://github.com/iamrahul25/arrow-escape/tree/85167e2c8c2f7273694cf58e0dd333917f2b0c4f" target="_blank" rel="noopener noreferrer">Arrow Escape</a> · MIT · <a href="/licenses/arcade-games.txt" target="_blank" rel="noopener noreferrer">开源许可</a></p>
      </aside>
    </div>
  </main>
</template>

<style scoped lang="scss" src="./SnakeEscapeGame.scss"></style>
