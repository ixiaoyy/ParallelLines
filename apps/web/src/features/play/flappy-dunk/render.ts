import { COURT, type DunkState, type Hoop } from "./rules";

/** 绘制一朵固定轮廓的云；使用世界位移实现慢速背景，不额外创建图片或动画资源。 */
function cloud(context: CanvasRenderingContext2D, x: number, y: number, scale: number): void {
  context.save();
  context.translate(x, y);
  context.scale(scale, scale);
  context.fillStyle = "#fffdf6";
  context.beginPath();
  context.ellipse(0, 0, 39, 14, 0, 0, Math.PI * 2);
  context.ellipse(-15, -9, 18, 18, 0, 0, Math.PI * 2);
  context.ellipse(10, -17, 23, 23, 0, 0, Math.PI * 2);
  context.fill();
  context.restore();
}

/** 自绘奶油色运动场和缓慢移动的云，所有背景元素均无碰撞效果。 */
function background(context: CanvasRenderingContext2D, distance: number): void {
  context.fillStyle = "#fbefd6";
  context.fillRect(0, 0, COURT.width, COURT.height);
  const wash = context.createLinearGradient(0, 0, 0, COURT.floor);
  wash.addColorStop(0, "#f8e4b8");
  wash.addColorStop(0.7, "#fff7e7");
  wash.addColorStop(1, "#f6e7c6");
  context.fillStyle = wash;
  context.fillRect(0, COURT.ceiling, COURT.width, COURT.floor - COURT.ceiling);

  // 背景滚动只取余数，长时间游玩不会累积无限数量的场景对象。
  for (let index = 0; index < 4; index += 1) {
    const x = ((index * 184 + 80 - distance * 0.12) % 736 + 736) % 736 - 110;
    cloud(context, x, 148 + (index % 2) * 82, 0.7 + (index % 3) * 0.15);
  }
  context.strokeStyle = "#e3c998";
  context.lineWidth = 2;
  context.globalAlpha = 0.4;
  for (let index = -1; index < 5; index += 1) {
    const x = index * 174 - (distance * 0.22) % 174;
    context.beginPath();
    context.moveTo(x, 520);
    context.lineTo(x - 90, COURT.floor);
    context.stroke();
  }
  context.beginPath();
  context.ellipse(260 - (distance * 0.1) % 80, 592, 145, 43, 0, 0, Math.PI * 2);
  context.stroke();
  context.globalAlpha = 1;

  context.fillStyle = "#d3a75c";
  context.fillRect(0, 0, COURT.width, COURT.ceiling);
  context.fillRect(0, COURT.floor, COURT.width, COURT.height - COURT.floor);
  context.fillStyle = "#f1ce80";
  context.fillRect(0, COURT.ceiling - 10, COURT.width, 10);
  context.fillRect(0, COURT.floor, COURT.width, 11);
  context.strokeStyle = "#a98042";
  context.lineWidth = 2;
  for (let x = -(distance * 0.4) % 80; x < COURT.width; x += 80) {
    context.beginPath();
    context.moveTo(x, COURT.floor + 11);
    context.lineTo(x - 23, COURT.height);
    context.stroke();
  }
}

/** 分两层绘制篮圈，球在前后层之间渲染，形成从上方入圈的视觉深度。 */
function hoopPart(context: CanvasRenderingContext2D, hoop: Hoop, front: boolean): void {
  const start = front ? 0 : Math.PI;
  const end = front ? Math.PI : Math.PI * 2;
  context.save();
  context.translate(hoop.x, hoop.y);
  if (!front) {
    context.strokeStyle = hoop.scored ? "#85b8a0" : "#d9af83";
    context.lineWidth = 1.5;
    context.globalAlpha = 0.55;
    // 篮网仅装饰；命中范围始终按篮圈两端及上下入口计算。
    for (let index = 0; index < 7; index += 1) {
      const x = -hoop.halfWidth + 12 + index * (hoop.halfWidth * 2 - 24) / 6;
      context.beginPath();
      context.moveTo(x, 5);
      context.lineTo(x * 0.68, 54);
      context.stroke();
    }
    for (const y of [23, 40, 53]) {
      context.beginPath();
      context.ellipse(0, y, hoop.halfWidth * (1 - y * 0.005), 7, 0, 0, Math.PI);
      context.stroke();
    }
    context.globalAlpha = 1;
  }
  context.lineCap = "round";
  context.lineWidth = 13;
  context.strokeStyle = hoop.scored ? "#33896d" : "#9d342a";
  context.beginPath();
  context.ellipse(0, 0, hoop.halfWidth, 12, 0, start, end);
  context.stroke();
  context.lineWidth = 7;
  context.strokeStyle = hoop.scored ? "#79c69b" : front ? "#f75a40" : "#e0442e";
  context.beginPath();
  context.ellipse(0, -1.5, hoop.halfWidth, 12, 0, start, end);
  context.stroke();
  context.restore();
}

/** 绘制白色小翅膀；翅膀随竖直速度摆动，只影响外观。 */
function wing(context: CanvasRenderingContext2D, direction: number, velocity: number): void {
  context.save();
  context.scale(direction, 1);
  context.rotate(Math.max(-0.2, Math.min(0.45, -velocity / 900)));
  context.fillStyle = "#fffefa";
  context.strokeStyle = "#61372a";
  context.lineWidth = 2.5;
  context.beginPath();
  context.moveTo(10, -9);
  context.bezierCurveTo(25, -12, 34, -23, 42, -31);
  context.bezierCurveTo(48, -8, 41, -1, 36, -1);
  context.bezierCurveTo(40, 8, 27, 15, 20, 7);
  context.bezierCurveTo(14, 9, 10, 4, 10, -9);
  context.fill();
  context.stroke();
  context.strokeStyle = "#dac4a6";
  context.lineWidth = 1.2;
  context.beginPath();
  context.moveTo(23, 0);
  context.quadraticCurveTo(34, -5, 38, -15);
  context.stroke();
  context.restore();
}

/** 自绘带翅膀的篮球与高光，碰撞体固定为中心圆，不包含装饰翅膀。 */
function ball(context: CanvasRenderingContext2D, state: DunkState): void {
  context.save();
  context.translate(COURT.ballX, state.ballY);
  wing(context, -1, state.velocityY);
  wing(context, 1, state.velocityY);
  context.rotate(Math.max(-0.3, Math.min(0.35, state.velocityY / 1300)));
  const color = context.createRadialGradient(-7, -8, 2, 0, 0, 22);
  color.addColorStop(0, "#ffc362");
  color.addColorStop(0.55, "#f79332");
  color.addColorStop(1, "#d96523");
  context.fillStyle = color;
  context.strokeStyle = "#623426";
  context.lineWidth = 2.7;
  context.beginPath();
  context.arc(0, 0, COURT.radius, 0, Math.PI * 2);
  context.fill();
  context.stroke();
  context.lineWidth = 1.9;
  context.beginPath();
  context.moveTo(-18, -1);
  context.lineTo(18, -1);
  context.moveTo(1, -18);
  context.lineTo(1, 18);
  context.moveTo(-12, -13);
  context.bezierCurveTo(-3, -4, -3, 5, -12, 13);
  context.moveTo(12, -13);
  context.bezierCurveTo(5, -5, 5, 7, 12, 13);
  context.stroke();
  context.fillStyle = "#ffe8a6";
  context.beginPath();
  context.ellipse(-6, -10, 4, 2, -0.7, 0, Math.PI * 2);
  context.fill();
  context.restore();
}

/** 用逻辑尺寸绘制当前帧；调用方预先设置 DPR/缩放，不读取 DOM 或修改游戏状态。 */
export function drawDunkCourt(context: CanvasRenderingContext2D, state: DunkState): void {
  context.clearRect(0, 0, COURT.width, COURT.height);
  background(context, state.distance);
  for (const hoop of state.hoops) hoopPart(context, hoop, false);
  ball(context, state);
  for (const hoop of state.hoops) hoopPart(context, hoop, true);

  // 进行中只显示操作提示和下一个篮圈方向，避免遮住球的飞行路线。
  if (state.phase === "ready") {
    context.strokeStyle = "#b29a70";
    context.lineWidth = 2;
    context.setLineDash([5, 7]);
    context.beginPath();
    context.moveTo(176, 292);
    context.bezierCurveTo(228, 230, 334, 250, 352, 335);
    context.stroke();
    context.setLineDash([]);
    context.fillStyle = "#b29a70";
    context.beginPath();
    context.moveTo(342, 332);
    context.lineTo(356, 346);
    context.lineTo(362, 328);
    context.fill();
  }
}
