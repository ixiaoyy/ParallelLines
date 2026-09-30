/** 飞翼灌篮使用固定逻辑尺寸；屏幕缩放只改变绘制，不改变碰撞和难度。 */
export const COURT = {
  width: 480,
  height: 720,
  ceiling: 42,
  floor: 670,
  ballX: 124,
  radius: 18,
  gravity: 900,
  flapVelocity: -340,
  maxFallVelocity: 620,
  rimRadius: 6,
  fixedStep: 1 / 120,
  maxFrame: 0.2,
} as const;

export type DunkPhase = "ready" | "running" | "paused" | "over";
export type LossReason = "ceiling" | "floor" | "wrong-way" | "missed" | null;

export interface Hoop {
  id: number;
  x: number;
  y: number;
  halfWidth: number;
  entered: boolean;
  scored: boolean;
  touched: boolean;
}

export interface DunkState {
  phase: DunkPhase;
  ballY: number;
  velocityY: number;
  hoops: Hoop[];
  score: number;
  passed: number;
  streak: number;
  lastPoints: number;
  loss: LossReason;
  elapsed: number;
  distance: number;
  nextHoopId: number;
}

/** 建立可随时重开的开局；第一只篮圈固定位置，便于学习点按节奏。 */
export function createDunkState(): DunkState {
  return {
    phase: "ready", ballY: 318, velocityY: 0,
    hoops: [{ id: 1, x: 358, y: 385, halfWidth: 67, entered: false, scored: false, touched: false }],
    score: 0, passed: 0, streak: 0, lastPoints: 0, loss: null,
    elapsed: 0, distance: 0, nextHoopId: 2,
  };
}

/** 点按或空格给予固定向上速度；暂停、结束时不接受球场输入。 */
export function flapDunk(state: DunkState): DunkState {
  if (state.phase === "paused" || state.phase === "over") return state;
  return { ...state, phase: "running", velocityY: COURT.flapVelocity };
}

/** 仅切换进行中与暂停状态；暂停时钟不会参与恢复后的物理计算。 */
export function toggleDunkPause(state: DunkState): DunkState {
  if (state.phase !== "running" && state.phase !== "paused") return state;
  return { ...state, phase: state.phase === "running" ? "paused" : "running" };
}

/** 按已穿过的篮圈数提升横向速度，最多 162，避免连击分数突然加速。 */
export function dunkSpeed(passed: number): number {
  return 114 + Math.min(Math.max(passed, 0), 24) * 2;
}

/** 求移动线段距原点的最近距离；用于高速运动时的篮圈端点碰撞。 */
function sweptDistance(ax: number, ay: number, bx: number, by: number): number {
  const dx = bx - ax;
  const dy = by - ay;
  const length = dx * dx + dy * dy;
  const factor = length === 0 ? 0 : Math.max(0, Math.min(1, -(ax * dx + ay * dy) / length));
  return Math.hypot(ax + dx * factor, ay + dy * factor);
}

/** 沿小步的球轨迹检查篮圈端点，触边只反弹并打断连击，不直接增加分数。 */
function collideRim(state: DunkState, hoop: Hoop, previousX: number, previousY: number): boolean {
  const limit = COURT.radius + COURT.rimRadius;
  for (const side of [-1, 1]) {
    const rimX = hoop.x + side * hoop.halfWidth;
    const previousRimX = previousX + side * hoop.halfWidth;
    if (sweptDistance(COURT.ballX - previousRimX, previousY - hoop.y,
      COURT.ballX - rimX, state.ballY - hoop.y) > limit) continue;

    // 球触到篮圈后退回接触的一侧；落下时轻弹，向上时反弹，防止穿透边缘。
    const above = previousY <= hoop.y;
    const horizontalGap = Math.min(limit, Math.abs(COURT.ballX - rimX));
    const verticalGap = Math.sqrt(Math.max(0, limit * limit - horizontalGap * horizontalGap)) + 0.1;
    state.ballY = hoop.y + (above ? -verticalGap : verticalGap);
    state.velocityY = above ? -Math.min(170, Math.abs(state.velocityY) * 0.55) : Math.max(100, Math.abs(state.velocityY) * 0.55);
    hoop.touched = true;
    hoop.entered = false;
    state.streak = 0;
    return true;
  }
  return false;
}

/** 插值求穿过给定水平线时的篮圈横坐标，判定完整球身是否位于圈内。 */
function fitsCrossing(hoop: Hoop, previousX: number, previousY: number, ballY: number, line: number): boolean {
  const ratio = (line - previousY) / (ballY - previousY);
  const crossingX = previousX + (hoop.x - previousX) * ratio;
  return Math.abs(COURT.ballX - crossingX) < hoop.halfWidth - COURT.radius - COURT.rimRadius;
}

/** 结束一局并保留当前分数；具体失败原因由界面按玩法提示呈现。 */
function lose(state: DunkState, reason: Exclude<LossReason, null>): void {
  state.phase = "over";
  state.loss = reason;
}

/** 补充视野内篮圈；随机值限制在合法区间，高度变化和圈宽都有难度上限。 */
function appendHoop(state: DunkState, random: () => number): void {
  const last = state.hoops.at(-1);
  if (!last || last.x > COURT.width + 120) return;
  const value = random();
  const fraction = Number.isFinite(value) ? Math.max(0, Math.min(value, 1)) : 0.5;
  const difficulty = Math.min(state.passed, 24);
  const spread = 90 + Math.min(difficulty * 3, 70);
  const y = Math.max(245, Math.min(490, last.y + (fraction * 2 - 1) * spread));
  state.hoops.push({
    id: state.nextHoopId++, x: last.x + 312, y,
    halfWidth: 67 - Math.min(difficulty, 20) * 0.4,
    entered: false, scored: false, touched: false,
  });
}

/** 推进一步游戏；最多模拟 0.2 秒、24 个小步，停顿与坏 dt 不会造成无上限循环。 */
export function advanceDunk(state: DunkState, seconds: number, random: () => number = Math.random): DunkState {
  if (state.phase !== "running" || !Number.isFinite(seconds) || seconds <= 0) return state;
  const duration = Math.min(seconds, COURT.maxFrame);
  const steps = Math.ceil(duration / COURT.fixedStep);
  const dt = duration / steps;
  const next: DunkState = { ...state, hoops: state.hoops.map((hoop) => ({ ...hoop })) };

  for (let index = 0; index < steps && next.phase === "running"; index += 1) {
    const previousY = next.ballY;
    const travel = dunkSpeed(next.passed) * dt;
    next.velocityY = Math.min(COURT.maxFallVelocity, next.velocityY + COURT.gravity * dt);
    next.ballY += next.velocityY * dt;
    next.elapsed += dt;
    next.distance += travel;
    for (const hoop of next.hoops) hoop.x -= travel;

    // 边界按球身判断；翅膀只是装饰，不参与碰撞，保留截图中的上下碰边规则。
    if (next.ballY - COURT.radius <= COURT.ceiling) {
      lose(next, "ceiling");
      break;
    }
    if (next.ballY + COURT.radius >= COURT.floor) {
      lose(next, "floor");
      break;
    }

    const hoop = next.hoops.find((candidate) => !candidate.scored);
    if (hoop) {
      const previousX = hoop.x + travel;
      const collided = collideRim(next, hoop, previousX, previousY);
      if (!collided) {
        // 从篮圈下方反向穿入会结束本局；已经计分的篮圈不再产生判定。
        if (previousY > hoop.y && next.ballY <= hoop.y &&
          fitsCrossing(hoop, previousX, previousY, next.ballY, hoop.y)) {
          lose(next, "wrong-way");
        }

        const entryLine = hoop.y - COURT.radius - COURT.rimRadius;
        if (previousY < entryLine && next.ballY >= entryLine &&
          fitsCrossing(hoop, previousX, previousY, next.ballY, entryLine)) hoop.entered = true;
        // 向上离开入圈线须取消入口状态，不能先探入再从侧面或反方向刷分。
        if (previousY >= entryLine && next.ballY < entryLine) hoop.entered = false;

        const exitLine = hoop.y + COURT.radius + COURT.rimRadius;
        if (next.phase === "running" && hoop.entered && previousY < exitLine && next.ballY >= exitLine &&
          fitsCrossing(hoop, previousX, previousY, next.ballY, exitLine)) {
          // 整球从上到下穿圈才计一次；干净入圈连续奖励最高 5 分，触边后回到 1 分。
          hoop.scored = true;
          next.passed += 1;
          next.streak = hoop.touched ? 0 : next.streak + 1;
          next.lastPoints = hoop.touched ? 1 : Math.min(next.streak, 5);
          next.score = Math.min(9_999_999, next.score + next.lastPoints);
        }
      }
      if (next.phase === "running" && !hoop.scored && hoop.x + hoop.halfWidth + COURT.radius < COURT.ballX) {
        lose(next, "missed");
      }
    }
    // 离场篮圈及时清理，列表长度始终有界；补圈只在需要时调用随机源。
    next.hoops = next.hoops.filter((hoop) => hoop.x + hoop.halfWidth >= -30);
    appendHoop(next, random);
  }
  return next;
}
