import { expect, test } from "@playwright/test";
import {
  LEVEL_COUNT, LEVEL_TIME_MS, availableSnakes, canEscape, createGame, createLevel,
  elapseTime, setPlaying, solveLevel, takeHint, tapSnake, type GameState, type Snake,
} from "../../src/features/play/snake-escape/rules";
import { parseProgress, unlockNext } from "../../src/features/play/snake-escape/storage";

/** 按蛇头真实行列定位，测试不依赖关卡存储编号或显示颜色。 */
function headName(snake: Snake): RegExp {
  const head = snake.path.at(-1)!;
  return new RegExp(`蛇头在第${head.y + 1}行第${head.x + 1}列，`);
}

/** 用单一头部阻挡构造局面，避免只用生成器自己的参考解测试生成器。 */
function blockedPosition(): GameState {
  const snakes: Snake[] = [
    { id: "blocked", active: true, path: [{ x: 1, y: 2 }, { x: 2, y: 2 }] },
    { id: "exit", active: true, path: [{ x: 3, y: 2 }, { x: 3, y: 1 }, { x: 3, y: 0 }] },
  ];
  return { ...setPlaying(createGame(1), true), level: { number: 1, gridSize: 5, seed: 0, snakes, solution: ["exit", "blocked"] }, snakes };
}

test("规则：全部固定关卡路径连续、无重叠且独立求解可通关", () => {
  expect(LEVEL_COUNT).toBe(50);
  for (let number = 1; number <= LEVEL_COUNT; number += 1) {
    const level = createLevel(number);
    const occupied = new Set<string>();
    for (const snake of level.snakes) {
      expect(snake.path.length, `第 ${number} 关 ${snake.id}`).toBeGreaterThanOrEqual(2);
      for (const [index, cell] of snake.path.entries()) {
        expect(cell.x).toBeGreaterThanOrEqual(0);
        expect(cell.y).toBeGreaterThanOrEqual(0);
        expect(cell.x).toBeLessThan(level.gridSize);
        expect(cell.y).toBeLessThan(level.gridSize);
        const key = `${cell.x},${cell.y}`;
        expect(occupied.has(key), `第 ${number} 关格子 ${key}`).toBe(false);
        occupied.add(key);
        if (index > 0) {
          const previous = snake.path[index - 1];
          expect(Math.abs(cell.x - previous.x) + Math.abs(cell.y - previous.y)).toBe(1);
        }
      }
    }
    const solution = solveLevel(level);
    expect(solution, `第 ${number} 关 seed=${level.seed}`).not.toBeNull();
    let state = setPlaying(createGame(number), true);
    for (const id of solution ?? []) {
      const result = tapSnake(state, id);
      expect(result.outcome).toBe("escaped");
      state = result.state;
    }
    expect(state.status).toBe("won");
    expect(state.lives).toBe(3);
    expect(createLevel(number)).toEqual(level);
  }
  expect(createLevel(50).gridSize).toBeGreaterThan(createLevel(1).gridSize);
  expect(createLevel(50).snakes.length).toBeGreaterThan(createLevel(1).snakes.length);
});

test("规则：撞退保留布局、扣一次生命，先放行阻挡蛇即可安全离场", () => {
  const state = blockedPosition();
  expect(canEscape(state.snakes[0], state.snakes, 5)).toBe(false);
  const blocked = tapSnake(state, "blocked");
  expect(blocked.outcome).toBe("blocked");
  expect(blocked.state.lives).toBe(2);
  expect(blocked.state.snakes).toBe(state.snakes);
  expect(state.lives).toBe(3);
  const opened = tapSnake(blocked.state, "exit");
  expect(opened.outcome).toBe("escaped");
  expect(tapSnake(opened.state, "blocked").state.status).toBe("won");
  expect(tapSnake(opened.state, "exit").outcome).toBe("ignored");
});

test("规则：三次撞击和超时准确失败，暂停与终局不再响应操作", () => {
  let state = blockedPosition();
  for (let count = 0; count < 3; count += 1) state = tapSnake(state, "blocked").state;
  expect(state.lives).toBe(0);
  expect(state.status).toBe("lost");
  expect(state.failure).toBe("lives");
  expect(tapSnake(state, "exit").state).toBe(state);
  expect(setPlaying(state, true)).toBe(state);
  const running = blockedPosition();
  const paused = setPlaying(running, false);
  expect(elapseTime(paused, LEVEL_TIME_MS)).toBe(paused);
  expect(tapSnake(paused, "exit").outcome).toBe("ignored");
  const resumed = setPlaying(paused, true);
  expect(elapseTime(resumed, LEVEL_TIME_MS - 1).remainingMs).toBe(1);
  const timedOut = elapseTime(resumed, LEVEL_TIME_MS);
  expect(timedOut.status).toBe("lost");
  expect(timedOut.failure).toBe("time");
  expect(timedOut.remainingMs).toBe(0);
  expect(elapseTime(resumed, Number.NaN)).toBe(resumed);
  expect(elapseTime(resumed, -1)).toBe(resumed);
});

test("规则：提示始终可离场，重复查看和结束后不消耗次数", () => {
  const state = blockedPosition();
  expect(availableSnakes(state).map((snake) => snake.id)).toEqual(["exit"]);
  const hinted = takeHint(state);
  expect(hinted.hintId).toBe("exit");
  expect(hinted.hints).toBe(2);
  expect(takeHint(hinted)).toBe(hinted);
  const won = tapSnake(tapSnake(hinted, "exit").state, "blocked").state;
  expect(takeHint(won)).toBe(won);
  expect(takeHint({ ...state, hints: 0 })).toEqual({ ...state, hints: 0 });
});

test("规则：进度数据损坏与越界恢复第一关，通关只解锁相邻一关", () => {
  for (const raw of [null, "broken", "null", "[]", '{"version":2,"highestUnlocked":4}', '{"version":1,"highestUnlocked":51}', '{"version":1,"highestUnlocked":2.5}']) {
    expect(parseProgress(raw)).toEqual({ version: 1, highestUnlocked: 1 });
  }
  const saved = parseProgress('{"version":1,"highestUnlocked":8}');
  expect(saved.highestUnlocked).toBe(8);
  expect(unlockNext(saved, 1).highestUnlocked).toBe(8);
  expect(unlockNext(saved, 8).highestUnlocked).toBe(9);
  expect(unlockNext(saved, 40)).toBe(saved);
  expect(unlockNext({ version: 1, highestUnlocked: 50 }, 50).highestUnlocked).toBe(50);
  expect(createGame(0).level.number).toBe(1);
  expect(createGame(Infinity).level.number).toBe(1);
  expect(createGame(999).level.number).toBe(50);
});

test("界面：手机可开局、撞退、提示、暂停、重开且棋盘触点不小于 44 像素", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/play/snake-escape");
  await expect(page.getByRole("heading", { name: "蛇蛇出洞" })).toBeVisible();
  await page.getByRole("button", { name: "开始游戏" }).click();
  const first = createGame(1);
  const blocked = first.snakes.find((snake) => !canEscape(snake, first.snakes, first.level.gridSize));
  expect(blocked).toBeDefined();
  const hit = page.locator(".se-board").getByRole("button", { name: headName(blocked!) });
  const size = await hit.boundingBox();
  expect(size?.width).toBeGreaterThanOrEqual(44);
  expect(size?.height).toBeGreaterThanOrEqual(44);
  await hit.click();
  await expect(page.getByLabel("剩余 2 条生命")).toBeVisible();
  await expect(page.getByRole("button", { name: /^提示/ })).toBeEnabled();
  await page.getByRole("button", { name: /^提示/ }).click();
  await expect(page.locator(".se-head-button--hint")).toHaveCount(1);
  await expect(page.locator(".se-arena__notice")).toHaveText("已圈出一条前方畅通的小蛇。");
  await page.getByRole("button", { name: "暂停", exact: true }).click();
  await expect(page.getByRole("heading", { name: "花园暂停营业" })).toBeVisible();
  await page.getByRole("button", { name: "继续游戏" }).click();
  await page.getByRole("button", { name: "重开", exact: true }).click();
  await expect(page.getByLabel("剩余 3 条生命")).toBeVisible();
  await expect(page.locator(".se-head-button--hint")).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.getByLabel("棋盘缩放").fill("160");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("界面：按安全顺序通关可进入下一关，刷新后保留已解锁进度", async ({ page }) => {
  await page.goto("/play/snake-escape");
  await page.getByRole("button", { name: "开始游戏" }).click();
  const level = createLevel(1);
  for (const id of solveLevel(level) ?? []) {
    const snake = level.snakes.find((candidate) => candidate.id === id)!;
    await page.locator(".se-board").getByRole("button", { name: headName(snake) }).click();
    // 离场显示期间输入被锁，下一条等待恢复，避免用测试绕过真实动画节奏。
    if (id !== (solveLevel(level) ?? []).at(-1)) await expect(page.getByRole("button", { name: /^提示/ })).toBeEnabled();
  }
  await expect(page.getByRole("heading", { name: "全部顺利出洞！" })).toBeVisible();
  await page.getByRole("button", { name: "下一关" }).click();
  await expect(page.locator(".se-hud__level")).toContainText("第 2 关");
  await page.reload();
  await expect(page.locator(".se-hud__level")).toContainText("第 2 关");
  await expect(page.getByLabel("去过的花园")).toHaveValue("2");
});

test("界面：320 像素密集关卡按真实头部格子命中，不误选重叠触点的小蛇", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 740 });
  await page.addInitScript(() => {
    localStorage.setItem("parallellines.snake-escape.progress.v1", JSON.stringify({ version: 1, highestUnlocked: 50 }));
  });
  await page.goto("/play/snake-escape");
  await page.getByRole("button", { name: "开始游戏" }).click();
  const level = createLevel(50);
  const snake = level.snakes[0];
  const head = snake.path.at(-1)!;
  expect(canEscape(snake, level.snakes, level.gridSize)).toBe(true);
  const point = await page.locator(".se-board__svg").evaluate((element, head) => {
    const matrix = (element as SVGSVGElement).getScreenCTM();
    if (!matrix) throw new Error("棋盘坐标不可用");
    const position = new DOMPoint(head.x + 0.5, head.y + 0.5).matrixTransform(matrix);
    return { x: position.x, y: position.y };
  }, head);
  await page.mouse.click(point.x, point.y);
  await expect(page.locator(".se-arena__notice")).toHaveText("小蛇出洞啦！");
  await expect(page.getByLabel("剩余 3 条生命")).toBeVisible();
  await expect(page.locator(".se-head-button")).toHaveCount(level.snakes.length - 1);
  await expect(page.locator(".se-board").getByRole("button", { name: headName(snake) })).toHaveCount(0);
  await expect(page.locator(".se-board").getByRole("button", { name: headName(level.snakes[16]) })).toHaveCount(1);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("界面：蛇头不显示解题编号，键盘按位置选择且离场后配色不变", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 740 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.addInitScript(() => {
    localStorage.setItem("parallellines.snake-escape.progress.v1", JSON.stringify({ version: 1, highestUnlocked: 5 }));
  });
  await page.goto("/play/snake-escape");
  await page.getByRole("button", { name: "开始游戏" }).click();
  const level = createLevel(5);
  const spatial = [...level.snakes].sort((a, b) => {
    const left = a.path.at(-1)!;
    const right = b.path.at(-1)!;
    return left.y - right.y || left.x - right.x;
  });
  expect(spatial.map((snake) => snake.id)).not.toEqual(level.solution);
  const heads = page.locator(".se-head-button");
  await expect(heads).toHaveCount(level.snakes.length);
  await expect(heads).toHaveText(level.snakes.map(() => ""));
  await expect(heads.locator("span")).toHaveCount(0);
  const labels = await heads.evaluateAll((elements) => elements.map((element) => element.getAttribute("aria-label")));
  for (const [index, snake] of spatial.entries()) expect(labels[index]).toMatch(headName(snake));
  await heads.first().focus();
  await page.keyboard.press("ArrowRight");
  await expect(heads.nth(1)).toBeFocused();
  await page.getByText("按位置选择小蛇", { exact: true }).click();
  const picker = page.locator(".se-snake-picker button");
  expect(await picker.evaluateAll((elements) => elements.map((element) => element.getAttribute("aria-label")))).toEqual(labels);
  const colorsBefore = await picker.locator("i").evaluateAll((elements) => elements.map((element) => (element as HTMLElement).style.background));
  const exit = level.snakes.find((snake) => canEscape(snake, level.snakes, level.gridSize))!;
  await page.locator(".se-snake-picker").getByRole("button", { name: headName(exit) }).click();
  await expect(heads).toHaveCount(level.snakes.length - 1);
  const remaining = spatial.filter((snake) => snake.id !== exit.id);
  const labelsAfter = await heads.evaluateAll((elements) => elements.map((element) => element.getAttribute("aria-label")));
  expect(labelsAfter).toEqual(labels.filter((_, index) => spatial[index].id !== exit.id));
  expect(await picker.locator("i").evaluateAll((elements) => elements.map((element) => (element as HTMLElement).style.background)))
    .toEqual(remaining.map((snake) => colorsBefore[spatial.indexOf(snake)]));
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
