import { describe, expect, it, vi } from "vitest";

import { drawPattern } from "./render";
import type { BeadColor } from "./palette";

const palette: BeadColor[] = [{ code: "S01", name: "S01", hex: "#ffffff", rgb: [255, 255, 255] }];

/** 只记录本次绘制需要的画布操作，不依赖浏览器或真实图像资源。 */
function makeCanvas() {
  const context = {} as CanvasRenderingContext2D;
  context.clearRect = vi.fn();
  context.fillRect = vi.fn();
  let width = 300;
  let height = 150;
  const widthWrites = vi.fn((value: number) => { width = value; });
  const heightWrites = vi.fn((value: number) => { height = value; });
  const canvas = {} as HTMLCanvasElement;
  Object.defineProperties(canvas, {
    width: { get: () => width, set: widthWrites },
    height: { get: () => height, set: heightWrites },
    getContext: { value: () => context },
  });
  return { canvas, context, widthWrites, heightWrites };
}

describe("拼豆画布缓冲复用", () => {
  it("相同尺寸重绘不重设缓冲，但每次清空旧像素", () => {
    const { canvas, context, widthWrites, heightWrites } = makeCanvas();
    const pattern = { width: 2, height: 1, cells: ["S01", null] };
    drawPattern(canvas, pattern, palette, { cellSize: 12 });
    drawPattern(canvas, pattern, palette, { cellSize: 12 });

    expect(widthWrites).toHaveBeenCalledExactlyOnceWith(24);
    expect(heightWrites).toHaveBeenCalledExactlyOnceWith(12);
    expect(context.clearRect).toHaveBeenCalledTimes(2);
    expect(context.clearRect).toHaveBeenLastCalledWith(0, 0, 24, 12);
  });

  it("擦除为透明空格时先清空旧像素，变化的尺寸仍更新缓冲", () => {
    const { canvas, context, widthWrites, heightWrites } = makeCanvas();
    drawPattern(canvas, { width: 1, height: 1, cells: ["S01"] }, palette, { cellSize: 12 });
    drawPattern(canvas, { width: 1, height: 1, cells: [null] }, palette, { cellSize: 12 });
    expect(context.fillRect).toHaveBeenCalledTimes(1);
    expect(context.clearRect).toHaveBeenCalledTimes(2);

    drawPattern(canvas, { width: 1, height: 1, cells: [null] }, palette, { cellSize: 24 });
    expect(widthWrites).toHaveBeenLastCalledWith(24);
    expect(heightWrites).toHaveBeenLastCalledWith(24);
    expect(context.clearRect).toHaveBeenLastCalledWith(0, 0, 24, 24);
  });
});
