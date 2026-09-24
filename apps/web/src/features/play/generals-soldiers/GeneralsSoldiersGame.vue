<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref } from "vue";

import UiButton from "@/shared/ui/Button.vue";

import type { AiRequest, AiResponse, Difficulty } from "./ai";
import {
  BOARD_SIZE,
  CELL_COUNT,
  createInitialState,
  legalMoves,
  playMove,
  positionKey,
  type GameState,
  type Move,
  type Side,
} from "./rules";

type Theme = "classic" | "china" | "modern" | "nature" | "tech";
type Phase = "setup" | "playing";

interface Snapshot {
  state: GameState;
  recentPositions: string[];
}

const difficulties: { value: Difficulty; label: string; detail: string }[] = [
  { value: "easy", label: "简单", detail: "轻松入门" },
  { value: "normal", label: "普通", detail: "会看回应" },
  { value: "hard", label: "困难", detail: "会防陷阱" },
  { value: "hell", label: "地狱", detail: "深度推演" },
];
const themes: { value: Theme; label: string }[] = [
  { value: "classic", label: "经典" },
  { value: "china", label: "中国风" },
  { value: "modern", label: "现代" },
  { value: "nature", label: "自然" },
  { value: "tech", label: "科技" },
];
const mascotArt = "/games/generals-soldiers/miaomiao-chibi.png";
const generalArt = "/games/generals-soldiers/general-chibi.png";
const soldierArt = "/games/generals-soldiers/soldier-chibi.png";
const previewBoard = createInitialState().board;
const OPENING_AI_DELAY_MS = 900;
const REPLY_AI_DELAY_MS = 500;

const phase = ref<Phase>("setup");
const playerSide = ref<Side>("soldier");
const difficulty = ref<Difficulty>("normal");
const theme = ref<Theme>("china");
const state = ref<GameState>(createInitialState());
const selected = ref<number | null>(null);
const aiThinking = ref(false);
const snapshots = ref<Snapshot[]>([]);
const recentPositions = ref<string[]>([positionKey(state.value)]);
const rulesDialog = ref<HTMLDialogElement | null>(null);
let aiWorker: Worker | null = null;
let aiTimer: number | null = null;
let aiStartTimer: number | null = null;
let aiRequestId = 0;

const availableMoves = computed(() =>
  phase.value === "playing" && state.value.turn === playerSide.value
    ? legalMoves(state.value)
    : [],
);
const selectedMoves = computed(() =>
  selected.value === null ? [] : availableMoves.value.filter((move) => move.from === selected.value),
);
const moveByDestination = computed(() =>
  new Map(selectedMoves.value.map((move) => [move.to, move])),
);
const jumpPathByCell = computed(() =>
  new Map(selectedMoves.value
    .filter((move) => move.capture)
    .map((move) => [(move.from + move.to) / 2, Math.abs(move.from - move.to) === BOARD_SIZE * 2 ? "vertical" : "horizontal"] as const)),
);
const playerWon = computed(() => state.value.winner === playerSide.value);
const round = computed(() => Math.floor(state.value.ply / 2));
const isPlayersTurn = computed(() => state.value.turn === playerSide.value && !aiThinking.value);
const miaomiaoLine = computed(() => {
  if (phase.value === "setup") return "选好阵营，我陪你研究下一步。";
  if (state.value.winner) return playerWon.value ? "这步走得漂亮！再来一局吗？" : "别灰心，再试一条棋路吧。";
  if (aiThinking.value && state.value.ply === 0) return "将军先走，先看清初始站位。";
  return aiThinking.value ? "电脑正在想下一步……" : "轮到你啦，看看哪里有机会。";
});

function stopAi(): void {
  aiRequestId += 1;
  aiWorker?.terminate();
  aiWorker = null;
  if (aiTimer !== null) window.clearTimeout(aiTimer);
  if (aiStartTimer !== null) window.clearTimeout(aiStartTimer);
  aiTimer = null;
  aiStartTimer = null;
  aiThinking.value = false;
}

function rememberPosition(next: GameState): void {
  recentPositions.value = [...recentPositions.value, positionKey(next)].slice(-14);
}

function finishAiMove(move: Move | null): void {
  const fallback = legalMoves(state.value)[0] ?? null;
  const chosen = move && legalMoves(state.value).some((candidate) => candidate.from === move.from && candidate.to === move.to)
    ? move
    : fallback;
  if (!chosen) {
    aiThinking.value = false;
    return;
  }
  const next = playMove(state.value, chosen.from, chosen.to);
  if (next) {
    state.value = next;
    rememberPosition(next);
  }
  aiThinking.value = false;
  // 兵方无棋可走时会自动跳过；若电脑仍执将军，就继续安排下一手。
  if (state.value.turn !== playerSide.value && !state.value.winner) scheduleAiMove();
}

function requestAiMove(): void {
  if (phase.value !== "playing" || state.value.winner || state.value.turn === playerSide.value) return;
  stopAi();
  aiThinking.value = true;
  const id = aiRequestId;
  let worker: Worker;
  try {
    worker = new Worker(new URL("./ai.worker.ts", import.meta.url), { type: "module" });
  } catch (error) {
    console.error("游戏电脑初始化失败", error);
    finishAiMove(null);
    return;
  }
  aiWorker = worker;
  const current = state.value;
  const request: AiRequest = {
    id,
    // Worker 的结构化克隆不接受 Vue Proxy，棋盘和上一步都转成普通数据。
    state: {
      board: [...current.board],
      turn: current.turn,
      soldiers: current.soldiers,
      ply: current.ply,
      winner: current.winner,
      lastMove: current.lastMove ? { ...current.lastMove } : null,
    },
    difficulty: difficulty.value,
    recentPositions: [...recentPositions.value],
  };

  worker.onmessage = (event: MessageEvent<AiResponse>) => {
    if (event.data.id !== aiRequestId) return;
    const move = event.data.move;
    stopAi();
    finishAiMove(move);
  };
  worker.onerror = (event) => {
    console.error("游戏电脑走棋失败", event);
    if (id !== aiRequestId) return;
    stopAi();
    finishAiMove(null);
  };
  // 搜索有固定预算；运行环境异常时终止后台计算并执行一手合法备用棋。
  aiTimer = window.setTimeout(() => {
    if (id !== aiRequestId) return;
    console.error("游戏电脑走棋超时");
    stopAi();
    finishAiMove(null);
  }, 3_500);
  try {
    worker.postMessage(request);
  } catch (error) {
    console.error("游戏电脑请求失败", error);
    stopAi();
    finishAiMove(null);
  }
}

function scheduleAiMove(): void {
  if (state.value.winner || state.value.turn === playerSide.value) return;
  aiThinking.value = true;
  // 开局先展示完整站位；后续电脑回应保留较短停顿，便于玩家辨认回合切换。
  const delay = state.value.ply === 0 ? OPENING_AI_DELAY_MS : REPLY_AI_DELAY_MS;
  aiStartTimer = window.setTimeout(() => {
    aiStartTimer = null;
    requestAiMove();
  }, delay);
}

function startGame(): void {
  stopAi();
  state.value = createInitialState();
  selected.value = null;
  snapshots.value = [];
  recentPositions.value = [positionKey(state.value)];
  phase.value = "playing";
  scheduleAiMove();
  // 设置页较长；进入对局后回到顶部，避免保留旧滚动位置让棋盘被截在屏幕外。
  void nextTick(() => window.scrollTo(0, 0));
}

function returnToSetup(): void {
  stopAi();
  selected.value = null;
  phase.value = "setup";
  void nextTick(() => window.scrollTo(0, 0));
}

function undoMove(): void {
  const snapshot = snapshots.value.pop();
  if (!snapshot) return;
  stopAi();
  state.value = snapshot.state;
  recentPositions.value = snapshot.recentPositions;
  selected.value = null;
}

function handleCellClick(index: number): void {
  if (phase.value !== "playing" || state.value.winner || !isPlayersTurn.value) return;
  if (state.value.board[index] === playerSide.value) {
    selected.value = selected.value === index ? null : index;
    return;
  }
  if (selected.value === null || !moveByDestination.value.has(index)) return;
  const next = playMove(state.value, selected.value, index);
  if (!next) return;

  // 悔棋回到玩家落子前的局面，电脑先行的开局因此会被保留。
  snapshots.value.push({ state: state.value, recentPositions: [...recentPositions.value] });
  selected.value = null;
  state.value = next;
  rememberPosition(next);
  scheduleAiMove();
}

function handleCellKeydown(index: number, event: KeyboardEvent): void {
  const delta = event.key === "ArrowUp" ? -BOARD_SIZE
    : event.key === "ArrowDown" ? BOARD_SIZE
      : event.key === "ArrowLeft" ? -1
        : event.key === "ArrowRight" ? 1 : 0;
  if (delta === 0) return;
  const column = index % BOARD_SIZE;
  if ((delta === -1 && column === 0) || (delta === 1 && column === BOARD_SIZE - 1)) return;
  const target = index + delta;
  if (target < 0 || target >= CELL_COUNT) return;
  event.preventDefault();
  const cells = (event.currentTarget as HTMLElement).parentElement?.querySelectorAll<HTMLButtonElement>(".gs-cell");
  cells?.[target]?.focus();
}

function cellLabel(index: number): string {
  const row = Math.floor(index / BOARD_SIZE) + 1;
  const column = index % BOARD_SIZE + 1;
  const piece = state.value.board[index] === "general" ? "将军"
    : state.value.board[index] === "soldier" ? "小兵" : "空格";
  const move = moveByDestination.value.get(index);
  const action = move ? move.capture ? "，可跳吃" : "，可落子" : "";
  const path = jumpPathByCell.value.has(index) ? "，跳吃路径" : "";
  return `第${row}行第${column}列，${piece}${action}${path}`;
}

function openRules(): void {
  rulesDialog.value?.showModal();
}

onBeforeUnmount(() => {
  stopAi();
});
</script>

<template>
  <div class="gs-page" :data-theme="theme" :data-phase="phase">
    <header class="gs-topline">
      <RouterLink :to="{ name: 'play-hub' }" class="gs-back">‹ 返回游乐场</RouterLink>
      <span class="gs-topline__label">平行线 · 游乐场</span>
      <button class="gs-topline__rules" type="button" @click="openRules">游戏规则</button>
    </header>

    <div v-if="phase === 'setup'" class="gs-setup">
      <section class="gs-hero" aria-labelledby="gs-title">
        <div class="gs-hero__copy">
          <span class="gs-hero__eyebrow">喵喵酱的棋局手帖</span>
          <h1 id="gs-title">将军战小兵</h1>
          <p>三位将军，十五名小兵。你要突围吃子，还是一步步完成围困？</p>
          <div class="gs-preview" aria-label="初始棋盘预览">
            <span
              v-for="(cell, index) in previewBoard"
              :key="index"
              class="gs-preview__cell"
              :class="`gs-preview__cell--${cell}`"
              aria-hidden="true"
            >
              <img v-if="cell !== 'empty'" :src="cell === 'general' ? generalArt : soldierArt" alt="" width="320" height="320" />
            </span>
          </div>
        </div>
        <div class="gs-hero__character">
          <img :src="mascotArt" alt="Q 版喵喵酱手持将军和小兵棋子" width="760" height="827" />
          <p class="gs-character-line">{{ miaomiaoLine }}</p>
        </div>
      </section>

      <section class="gs-settings" aria-label="对局设置">
        <div class="gs-setting-group">
          <div class="gs-setting-group__head"><h2>选择阵营</h2><span>电脑会执另一方</span></div>
          <div class="gs-roles">
            <button type="button" class="gs-role gs-role--general" :class="{ 'gs-role--selected': playerSide === 'general' }" :aria-pressed="playerSide === 'general'" @click="playerSide = 'general'">
              <span class="gs-role__symbol gs-role__symbol--general" aria-hidden="true"><img :src="generalArt" alt="" width="320" height="320" /></span>
              <span><strong>将军方</strong><small>3 枚棋子 · 突围吃兵</small></span>
            </button>
            <button type="button" class="gs-role gs-role--soldier" :class="{ 'gs-role--selected': playerSide === 'soldier' }" :aria-pressed="playerSide === 'soldier'" @click="playerSide = 'soldier'">
              <span class="gs-role__symbol gs-role__symbol--soldier" aria-hidden="true"><img :src="soldierArt" alt="" width="320" height="320" /></span>
              <span><strong>小兵方</strong><small>15 枚棋子 · 合力围困</small></span>
            </button>
          </div>
        </div>

        <div class="gs-setting-group">
          <div class="gs-setting-group__head"><h2>电脑难度</h2><span>四档真实走棋策略</span></div>
          <div class="gs-difficulties">
            <button v-for="option in difficulties" :key="option.value" type="button" class="gs-difficulty" :class="{ 'gs-difficulty--selected': difficulty === option.value }" :aria-pressed="difficulty === option.value" @click="difficulty = option.value">
              <strong>{{ option.label }}</strong><small>{{ option.detail }}</small>
            </button>
          </div>
        </div>

        <div class="gs-setting-group">
          <div class="gs-setting-group__head"><h2>棋盘皮肤</h2><span>只改变外观，不改变规则</span></div>
          <div class="gs-themes">
            <button v-for="option in themes" :key="option.value" type="button" class="gs-theme-option" :class="{ 'gs-theme-option--selected': theme === option.value }" :aria-pressed="theme === option.value" @click="theme = option.value">
              <span class="gs-theme-preview" :data-theme="option.value" aria-hidden="true"><i v-for="index in 25" :key="index"></i></span>
              <span>{{ option.label }}</span>
            </button>
          </div>
        </div>

        <div class="gs-settings__foot">
          <UiButton tone="primary" class="gs-start" @click="startGame">开始对弈 <span aria-hidden="true">→</span></UiButton>
          <p>将军先行；选小兵方时由电脑先走。</p>
        </div>
      </section>
    </div>

    <div v-else class="gs-match">
      <header class="gs-match__header">
        <div><span class="gs-match__kicker">第 {{ round }} 回合 · 你执{{ playerSide === 'general' ? '将军' : '小兵' }}</span><h1>将军战小兵</h1></div>
        <span class="gs-turn" role="status">{{ state.winner ? '对局结束' : aiThinking ? state.ply === 0 ? '将军先行 · 电脑准备中' : '电脑思考中' : '轮到你走' }}</span>
      </header>

      <div class="gs-match__body">
        <aside class="gs-match__aside gs-match__aside--character">
          <div class="gs-miaomiao-portrait"><img :src="mascotArt" alt="喵喵酱" width="760" height="827" /></div>
          <p class="gs-match__speech" role="status">{{ miaomiaoLine }}</p>
          <p class="gs-match__side">你执{{ playerSide === 'general' ? '将军' : '小兵' }} · {{ difficulties.find((item) => item.value === difficulty)?.label }}</p>
        </aside>

        <div class="gs-arena">
          <div class="gs-score" aria-label="棋子数量">
            <span><i class="gs-score__piece gs-score__piece--general"><img :src="generalArt" alt="" width="320" height="320" /></i><strong>3</strong><small>将军</small></span>
            <span class="gs-score__versus">对 战</span>
            <span><i class="gs-score__piece gs-score__piece--soldier"><img :src="soldierArt" alt="" width="320" height="320" /></i><strong>{{ state.soldiers }}</strong><small>小兵</small></span>
          </div>

          <div class="gs-board-frame">
            <div class="gs-board" aria-label="五乘五棋盘">
              <button
                v-for="(cell, index) in state.board"
                :key="index"
                type="button"
                class="gs-cell"
                :class="{
                  'gs-cell--selected': selected === index,
                  'gs-cell--move': moveByDestination.get(index) && !moveByDestination.get(index)?.capture,
                  'gs-cell--capture': moveByDestination.get(index)?.capture,
                  'gs-cell--jump-path': jumpPathByCell.has(index),
                  'gs-cell--last-from': state.lastMove?.from === index,
                  'gs-cell--last': state.lastMove?.to === index,
                }"
                :aria-label="cellLabel(index)"
                :aria-pressed="selected === index"
                @click="handleCellClick(index)"
                @keydown="handleCellKeydown(index, $event)"
              >
                <span v-if="jumpPathByCell.has(index)" class="gs-cell__path" :class="`gs-cell__path--${jumpPathByCell.get(index)}`" aria-hidden="true"></span>
                <span v-if="cell !== 'empty'" class="gs-piece" :class="`gs-piece--${cell}`">
                  <span class="gs-piece__portrait" aria-hidden="true"><img :src="cell === 'general' ? generalArt : soldierArt" alt="" width="320" height="320" /></span>
                  <b class="gs-piece__glyph" aria-hidden="true">{{ cell === 'general' ? '将' : '兵' }}</b>
                </span>
                <span v-else-if="moveByDestination.get(index)" class="gs-cell__dot" aria-hidden="true"></span>
              </button>
            </div>
            <div v-if="state.winner" class="gs-result" :class="playerWon ? 'gs-result--win' : 'gs-result--lose'" role="status">
              <img
                :src="playerWon ? '/games/generals-soldiers/miaomiao-win.png' : '/games/generals-soldiers/miaomiao-try-again.png'"
                alt=""
                width="560"
                height="610"
              />
              <div class="gs-result__copy">
                <span>{{ playerWon ? '喵！赢啦！' : '喵呜，再来！' }}</span>
                <strong>{{ state.winner === 'general' ? '将军方获胜' : '小兵方获胜' }}</strong>
                <p>{{ state.winner === 'general' ? '小兵已剩 3 枚或更少。' : '三位将军都被围住了。' }}</p>
                <div class="gs-result__actions">
                  <UiButton tone="primary" @click="startGame">再来一局</UiButton>
                  <button type="button" @click="returnToSetup">换阵营</button>
                </div>
              </div>
            </div>
          </div>

          <div class="gs-match__hint" aria-label="棋盘标记说明"><span>落点</span><i aria-hidden="true"></i><span>跳吃</span><b aria-hidden="true"></b><span>连线为跳吃路径</span></div>

          <div class="gs-match-actions">
            <button type="button" :disabled="snapshots.length === 0" @click="undoMove">悔棋</button>
            <button type="button" @click="openRules">规则</button>
            <button type="button" @click="startGame">重来</button>
            <button type="button" @click="returnToSetup">设置</button>
          </div>
        </div>

        <aside class="gs-match__aside gs-match__aside--info">
          <strong>这局的目标</strong>
          <p v-if="playerSide === 'general'">隔一个空格跳吃小兵，直到场上小兵不超过 3 枚。</p>
          <p v-else>把三位将军都围住，让他们无法移动或跳吃。</p>
        </aside>
      </div>
    </div>

    <dialog ref="rulesDialog" class="gs-rules-dialog" aria-labelledby="gs-rules-title">
      <h2 id="gs-rules-title">游戏规则</h2>
      <p>5×5 棋盘。三位将军位于底行中间，十五名小兵占据顶部三行；将军先走。</p>
      <ul>
        <li>双方每手只移动一枚棋子，向上下左右走一格，目标必须为空。</li>
        <li>将军可跳过相邻的一个空格，落到第二格的小兵位置并吃掉它；小兵不能吃将军。</li>
        <li>小兵剩 3 枚或更少时，将军胜；三位将军都无法移动和跳吃时，小兵胜。</li>
      </ul>
      <form method="dialog"><UiButton tone="primary" type="submit">明白了</UiButton></form>
    </dialog>
  </div>
</template>

<style scoped lang="scss" src="./GeneralsSoldiersGame.scss"></style>
