import { expect, test } from "@playwright/test";
import { advanceDunk, COURT, createDunkState, dunkSpeed, flapDunk, toggleDunkPause, type DunkState } from "../../src/features/play/flappy-dunk/rules";
import { parseDunkBest } from "../../src/features/play/flappy-dunk/storage";

/** 建立只有一只目标篮圈的可复现局面，测试不依赖随机后续场景。 */
function position(ballY: number, velocityY: number, hoopX = COURT.ballX): DunkState {
  const state = createDunkState();
  state.phase = "running";
  state.ballY = ballY;
  state.velocityY = velocityY;
  state.hoops[0]!.x = hoopX;
  return state;
}

test("首次点按开始、连续点按重置向上速度，暂停和结束不接受点按", () => {
  const ready = createDunkState();
  expect(advanceDunk(ready, 0.2)).toBe(ready);
  const running = flapDunk(ready);
  expect(running.phase).toBe("running");
  expect(running.velocityY).toBe(COURT.flapVelocity);
  expect(ready.phase).toBe("ready");
  expect(flapDunk({ ...running, velocityY: 500 }).velocityY).toBe(COURT.flapVelocity);

  const paused = toggleDunkPause(running);
  expect(paused.phase).toBe("paused");
  expect(advanceDunk(paused, 4)).toBe(paused);
  expect(flapDunk(paused)).toBe(paused);
  expect(toggleDunkPause(paused).ballY).toBe(running.ballY);
  expect(toggleDunkPause(ready)).toBe(ready);
  const over = { ...running, phase: "over" as const };
  expect(flapDunk(over)).toBe(over);
});

test("整球从上到下穿圈仅计一次，已计分圈不再触发反向失败", () => {
  const initial = position(350, 260);
  const result = advanceDunk(initial, 0.2, () => 0.5);
  expect(result.phase).toBe("running");
  expect(result.hoops[0]!.scored).toBe(true);
  expect(result.score).toBe(1);
  expect(result.passed).toBe(1);
  expect(initial.hoops[0]!.scored).toBe(false);

  const next = advanceDunk(flapDunk(result), 0.2, () => 0.5);
  expect(next.score).toBe(1);
  expect(next.passed).toBe(1);
  expect(next.loss).toBeNull();
});

test("先进入上沿但整球尚未穿完时不提前计分", () => {
  const result = advanceDunk(position(350, 200), 0.1, () => 0.5);
  expect(result.hoops[0]!.entered).toBe(true);
  expect(result.hoops[0]!.scored).toBe(false);
  expect(result.score).toBe(0);
});

test("从下方反向穿圈和漏掉未计分篮圈会明确结束一局", () => {
  const wrongWay = advanceDunk(position(418, -340), 0.2, () => 0.5);
  expect(wrongWay.phase).toBe("over");
  expect(wrongWay.loss).toBe("wrong-way");
  expect(wrongWay.score).toBe(0);

  const missed = advanceDunk(position(220, 0, 40), 0.05, () => 0.5);
  expect(missed.phase).toBe("over");
  expect(missed.loss).toBe("missed");
});

test("球身碰天花板或地板结束，翅膀不扩大边界碰撞体", () => {
  expect(advanceDunk(position(68, -340, 1100), 0.05).loss).toBe("ceiling");
  expect(advanceDunk(position(646, 300, 1100), 0.05).loss).toBe("floor");
  expect(advanceDunk(position(74, 0, 1100), 0.01).phase).toBe("running");
});

test("高速轨迹不会穿透篮圈端点，触边反弹且断连击", () => {
  const initial = position(345, 620, COURT.ballX + 67);
  initial.streak = 4;
  const result = advanceDunk(initial, 0.1, () => 0.5);
  expect(result.hoops[0]!.touched).toBe(true);
  expect(result.hoops[0]!.scored).toBe(false);
  expect(result.score).toBe(0);
  expect(result.streak).toBe(0);
  expect(result.ballY).toBeLessThan(385);
});

test("长帧仍检查上下入圈，坏时间不推进，单次模拟和场景数量有上限", () => {
  const highSpeed = advanceDunk(position(330, 620), 0.2, () => 0.5);
  expect(highSpeed.score).toBe(1);
  const initial = position(200, 0, 1100);
  const bounded = advanceDunk(initial, 300, () => 0.5);
  expect(bounded.elapsed).toBeCloseTo(0.2, 9);
  expect(bounded.hoops.length).toBeLessThanOrEqual(3);
  for (const seconds of [NaN, Infinity, -1, 0]) expect(advanceDunk(initial, seconds)).toBe(initial);
});

test("空心连击奖励和速度有上限，触边后穿圈只记 1 分", () => {
  const clean = position(350, 260);
  clean.streak = 8;
  expect(advanceDunk(clean, 0.2, () => 0.5).lastPoints).toBe(5);
  const touched = position(350, 260);
  touched.hoops[0]!.touched = true;
  touched.streak = 8;
  const result = advanceDunk(touched, 0.2, () => 0.5);
  expect(result.lastPoints).toBe(1);
  expect(result.streak).toBe(0);
  expect(dunkSpeed(1_000)).toBe(dunkSpeed(24));
  expect(dunkSpeed(-1)).toBe(dunkSpeed(0));
});

test("最高分缓存拒绝负数、小数、异常数值和任意 JSON", () => {
  expect(parseDunkBest("0")).toBe(0);
  expect(parseDunkBest("125")).toBe(125);
  expect(parseDunkBest("9999999")).toBe(9_999_999);
  for (const value of [null, "", "-1", "1.5", "NaN", "Infinity", "1e3", "10000000", '{"score":10}', " 42 "]) {
    expect(parseDunkBest(value), String(value)).toBe(0);
  }
});
