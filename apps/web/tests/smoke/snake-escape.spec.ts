import { expect, test } from "@playwright/test";
import {
  LEVEL_COUNT, LEVEL_TIME_MS, availableSnakes, canEscape, createGame, createLevel,
  elapseTime, setPlaying, solveLevel, takeHint, tapSnake, type GameState, type Snake,
} from "../../src/features/play/snake-escape/rules";
import { parseProgress, unlockNext } from "../../src/features/play/snake-escape/storage";

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
  const index = first.snakes.findIndex((snake) => snake.id === blocked?.id);
  const hit = page.getByRole("button", { name: new RegExp(`^第 ${index + 1} 条`) });
  const size = await hit.boundingBox();
  expect(size?.width).toBeGreaterThanOrEqual(44);
  expect(size?.height).toBeGreaterThanOrEqual(44);
  await hit.click();
  await expect(page.getByLabel("剩余 2 条生命")).toBeVisible();
  await expect(page.getByRole("button", { name: /^提示/ })).toBeEnabled();
  await page.getByRole("button", { name: /^提示/ }).click();
  await expect(page.locator(".se-head-button--hint")).toHaveCount(1);
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
    const index = level.snakes.findIndex((snake) => snake.id === id);
    await page.getByRole("button", { name: new RegExp(`^第 ${index + 1} 条`) }).click();
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
  await expect(page.locator(".se-arena__notice")).toHaveText("第 1 条小蛇出洞啦！");
  await expect(page.getByLabel("剩余 3 条生命")).toBeVisible();
  await expect(page.locator(".se-head-button")).toHaveCount(level.snakes.length - 1);
  await expect(page.getByRole("button", { name: /^第 1 条/ })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /^第 17 条/ })).toHaveCount(1);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
