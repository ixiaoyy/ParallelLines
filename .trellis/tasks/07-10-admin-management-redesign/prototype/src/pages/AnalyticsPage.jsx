import { useEffect, useMemo, useRef, useState } from "react";
import {
  BranchesOutlined,
  CalendarOutlined,
  FileTextOutlined,
  ReloadOutlined,
  RiseOutlined,
  UserAddOutlined,
} from "@ant-design/icons";
import "./AnalyticsPage.css";

const RANGE_CONFIG = {
  7: { start: "2026-07-04", end: "2026-07-10", days: 7 },
  30: { start: "2026-06-11", end: "2026-07-10", days: 30 },
  90: { start: "2026-04-12", end: "2026-07-10", days: 90 },
};

const VISIT_DATA = [
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 15, 1, 4, 1, 5, 5, 30, 7, 14,
];

const VISITOR_DATA = [
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 1, 0, 1, 1, 2, 2, 5, 3, 3,
];

const GROWTH_DATA = [
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
];

const VISIT_CHART_CONFIG = {
  maxY: 35,
  yStep: 5,
  series: [
    { key: "visits", color: "#409eff" },
    { key: "visitors", color: "#10b981" },
  ],
};

const GROWTH_CHART_CONFIG = {
  maxY: 3,
  yStep: 1,
  series: [{ key: "growth", color: "#10b981" }],
};

const SOURCE_ROWS = [
  { label: "站内跳转", detail: "3 位访客", value: 45 },
  { label: "直接访问", detail: "18 位访客", value: 34 },
];

const ENTRY_ROWS = [
  { id: "home", label: "平行线", value: 42 },
  { id: "daily-quote-023", label: "每日金句｜第023天：你的善良，必须带点锋芒 · 微光手记 · 平行线", value: 4 },
  { id: "topic-detail-2418", label: "主题详情 · 平行线", value: 4 },
  { id: "absurd-poll-2026-07-08", label: "今日荒诞投票 07-08：如果首页多出一个神秘按钮 · 闲聊八卦 · 平行线", value: 3 },
  { id: "topic-detail-2386", label: "主题详情 · 平行线", value: 3 },
];

/**
 * Formats an ISO date for the compact Chinese admin date fields.
 * @param {string} value ISO date in YYYY-MM-DD format.
 * @returns {string} Date formatted as YYYY/MM/DD.
 */
function formatDate(value) {
  return value.replaceAll("-", "/");
}

/**
 * Builds axis labels between the selected range boundaries.
 * @param {{ start: string, days: number }} range Selected date range.
 * @returns {string[]} MM/DD labels for every day in the range.
 */
function buildDateLabels(range) {
  const start = new Date(`${range.start}T00:00:00Z`);

  return Array.from({ length: range.days }, (_, index) => {
    const date = new Date(start);
    date.setUTCDate(start.getUTCDate() + index);
    const month = String(date.getUTCMonth() + 1).padStart(2, "0");
    const day = String(date.getUTCDate()).padStart(2, "0");
    return `${month}/${day}`;
  });
}

/**
 * Fits the 30-day demo series to a selected preset without inventing activity.
 * @param {number[]} values Canonical 30-day values.
 * @param {number} days Number of days in the selected preset.
 * @returns {number[]} Series sliced or left-padded to the selected duration.
 */
function fitSeriesToRange(values, days) {
  if (days <= values.length) {
    return values.slice(values.length - days);
  }

  return [...Array(days - values.length).fill(0), ...values];
}

/**
 * Draws a responsive, accessible line chart into a native canvas element.
 * @param {HTMLCanvasElement | null} canvas Target canvas element.
 * @param {{ labels: string[], values: Record<string, number[]> }} model Chart labels and data.
 * @param {{ maxY: number, yStep: number, series: Array<{ key: string, color: string }> }} config Rendering configuration.
 * @returns {void} Updates only the canvas pixels.
 */
function drawLineChart(canvas, model, config) {
  if (!canvas) return;

  const rect = canvas.getBoundingClientRect();
  if (!rect.width || !rect.height) return;

  const pixelRatio = Math.min(window.devicePixelRatio || 1, 2);
  canvas.width = Math.round(rect.width * pixelRatio);
  canvas.height = Math.round(rect.height * pixelRatio);

  const context = canvas.getContext("2d");
  if (!context) return;

  context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
  context.clearRect(0, 0, rect.width, rect.height);

  const padding = { top: 14, right: 12, bottom: 34, left: 34 };
  const plotWidth = Math.max(0, rect.width - padding.left - padding.right);
  const plotHeight = Math.max(0, rect.height - padding.top - padding.bottom);

  context.lineWidth = 1;
  context.font = '11px "Inter", "PingFang SC", sans-serif';
  context.textBaseline = "middle";

  for (let value = 0; value <= config.maxY; value += config.yStep) {
    const y = padding.top + plotHeight - (value / config.maxY) * plotHeight;
    context.strokeStyle = "#e2e8f0";
    context.beginPath();
    context.moveTo(padding.left, y + 0.5);
    context.lineTo(padding.left + plotWidth, y + 0.5);
    context.stroke();

    context.fillStyle = "#64748b";
    context.textAlign = "right";
    context.fillText(String(value), padding.left - 9, y);
  }

  const tickCount = rect.width < 480 ? 4 : 7;
  for (let tick = 0; tick < tickCount; tick += 1) {
    const ratio = tickCount === 1 ? 0 : tick / (tickCount - 1);
    const index = Math.round(ratio * (model.labels.length - 1));
    const x = padding.left + ratio * plotWidth;
    context.fillStyle = "#64748b";
    context.textAlign = tick === 0 ? "left" : tick === tickCount - 1 ? "right" : "center";
    context.fillText(model.labels[index], x, padding.top + plotHeight + 20);
  }

  config.series.forEach((line) => {
    const values = model.values[line.key] || [];
    const points = values.map((value, index) => ({
      x: padding.left + (index / Math.max(values.length - 1, 1)) * plotWidth,
      y: padding.top + plotHeight - (value / config.maxY) * plotHeight,
    }));

    if (!points.length) return;

    context.strokeStyle = line.color;
    context.lineWidth = 2.25;
    context.lineCap = "round";
    context.lineJoin = "round";
    context.beginPath();
    context.moveTo(points[0].x, points[0].y);

    for (let index = 1; index < points.length; index += 1) {
      const previous = points[index - 1];
      const current = points[index];
      const midpointX = (previous.x + current.x) / 2;
      context.bezierCurveTo(midpointX, previous.y, midpointX, current.y, current.x, current.y);
    }

    context.stroke();
  });
}

/**
 * Keeps a native canvas chart sharp and correctly sized as its panel changes.
 * @param {React.RefObject<HTMLCanvasElement | null>} canvasRef Canvas reference.
 * @param {{ labels: string[], values: Record<string, number[]> }} model Chart model.
 * @param {{ maxY: number, yStep: number, series: Array<{ key: string, color: string }> }} config Chart configuration.
 * @returns {void} Registers and cleans up resize observation.
 */
function useResponsiveChart(canvasRef, model, config) {
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return undefined;

    /** Redraws the chart using the canvas's latest rendered dimensions. */
    const render = () => drawLineChart(canvas, model, config);
    render();

    const observer = new ResizeObserver(render);
    observer.observe(canvas);

    return () => observer.disconnect();
  }, [canvasRef, config, model]);
}

/**
 * Renders the selected operations-console analytics direction as a standalone page.
 * @returns {JSX.Element} Interactive access and user-growth prototype.
 */
export function AnalyticsPage() {
  const [activeRange, setActiveRange] = useState(30);
  const [refreshState, setRefreshState] = useState("idle");
  const refreshTimersRef = useRef([]);
  const visitCanvasRef = useRef(null);
  const growthCanvasRef = useRef(null);
  const range = RANGE_CONFIG[activeRange];

  const labels = useMemo(() => buildDateLabels(range), [range]);
  const visitModel = useMemo(
    () => ({
      labels,
      values: {
        visits: fitSeriesToRange(VISIT_DATA, range.days),
        visitors: fitSeriesToRange(VISITOR_DATA, range.days),
      },
    }),
    [labels, range.days],
  );
  const growthModel = useMemo(
    () => ({
      labels,
      values: { growth: fitSeriesToRange(GROWTH_DATA, range.days) },
    }),
    [labels, range.days],
  );

  useResponsiveChart(visitCanvasRef, visitModel, VISIT_CHART_CONFIG);
  useResponsiveChart(growthCanvasRef, growthModel, GROWTH_CHART_CONFIG);

  useEffect(
    () => () => refreshTimersRef.current.forEach((timer) => window.clearTimeout(timer)),
    [],
  );

  /**
   * Activates a date preset and immediately updates its visible range.
   * @param {number} days Preset duration in days.
   * @returns {void}
   */
  function handleRangeChange(days) {
    setActiveRange(days);
  }

  /**
   * Simulates a short refresh cycle and exposes its result to assistive technology.
   * @returns {void}
   */
  function handleRefresh() {
    if (refreshState === "refreshing") return;

    refreshTimersRef.current.forEach((timer) => window.clearTimeout(timer));
    setRefreshState("refreshing");

    refreshTimersRef.current = [
      window.setTimeout(() => setRefreshState("done"), 720),
      window.setTimeout(() => setRefreshState("idle"), 1900),
    ];
  }

  const refreshLabel =
    refreshState === "refreshing" ? "刷新中" : refreshState === "done" ? "已更新" : "刷新";

  return (
    <section className="analytics-page" aria-labelledby="analytics-title">
      <header className="analytics-page__header">
        <div>
          <h1 id="analytics-title">访问与用户增长</h1>
          <p>查看所选日期范围内的访问表现与真实用户增长。</p>
        </div>
        <button
          className={`analytics-refresh${refreshState === "done" ? " is-done" : ""}`}
          type="button"
          aria-label={refreshLabel}
          onClick={handleRefresh}
          disabled={refreshState === "refreshing"}
        >
          <ReloadOutlined className={refreshState === "refreshing" ? "is-spinning" : ""} />
          <span>{refreshLabel}</span>
        </button>
        <span className="analytics-page__status" aria-live="polite">
          {refreshState === "done" ? "数据已更新" : refreshState === "refreshing" ? "正在刷新数据" : ""}
        </span>
      </header>

      <div className="analytics-toolbar" aria-label="统计日期范围">
        <div className="analytics-presets" aria-label="日期预设">
          {[7, 30, 90].map((days) => (
            <button
              key={days}
              type="button"
              className={activeRange === days ? "is-active" : ""}
              aria-pressed={activeRange === days}
              onClick={() => handleRangeChange(days)}
            >
              {days} 天
            </button>
          ))}
        </div>

        <span className="analytics-toolbar__divider" aria-hidden="true" />

        <div className="analytics-date-fields">
          <label>
            <span>开始日期</span>
            <span className="analytics-date-input">
              <input type="text" value={formatDate(range.start)} readOnly />
              <CalendarOutlined aria-hidden="true" />
            </span>
          </label>
          <label>
            <span>结束日期</span>
            <span className="analytics-date-input">
              <input type="text" value={formatDate(range.end)} readOnly />
              <CalendarOutlined aria-hidden="true" />
            </span>
          </label>
        </div>
      </div>

      <div className="analytics-metrics" aria-label="核心指标">
        <article className="analytics-metric">
          <span>访问量</span>
          <strong>79</strong>
        </article>
        <article className="analytics-metric">
          <span>独立访客</span>
          <div className="analytics-metric__value">
            <strong>18</strong>
          </div>
        </article>
        <article className="analytics-metric">
          <span>区间新增用户</span>
          <div className="analytics-metric__value">
            <strong>2</strong>
            <small>不含马甲账号</small>
            <UserAddOutlined className="analytics-metric__icon is-green" aria-hidden="true" />
          </div>
        </article>
        <article className="analytics-metric">
          <span>日均新增</span>
          <div className="analytics-metric__value">
            <strong>0.1</strong>
            <RiseOutlined className="analytics-metric__icon is-purple" aria-hidden="true" />
          </div>
        </article>
        <article className="analytics-metric">
          <span>引流访问</span>
          <div className="analytics-metric__value">
            <strong>0</strong>
            <BranchesOutlined className="analytics-metric__icon" aria-hidden="true" />
          </div>
        </article>
        <article className="analytics-metric">
          <span>新增内容</span>
          <div className="analytics-metric__value">
            <strong>101</strong>
            <FileTextOutlined className="analytics-metric__icon is-orange" aria-hidden="true" />
          </div>
        </article>
      </div>

      <div className="analytics-charts">
        <section className="analytics-chart-panel" aria-labelledby="visits-chart-title">
          <h2 id="visits-chart-title">站点访问趋势</h2>
          <canvas
            ref={visitCanvasRef}
            className="analytics-chart"
            role="img"
            aria-label={`${formatDate(range.start)} 至 ${formatDate(range.end)} 的访问量与独立访客折线图`}
          />
          <div className="analytics-legend" aria-hidden="true">
            <span><i className="is-blue" />访问量</span>
            <span><i className="is-green" />独立访客</span>
          </div>
        </section>

        <section className="analytics-chart-panel analytics-chart-panel--growth" aria-labelledby="growth-chart-title">
          <h2 id="growth-chart-title">用户增长趋势</h2>
          <canvas
            ref={growthCanvasRef}
            className="analytics-chart"
            role="img"
            aria-label={`${formatDate(range.start)} 至 ${formatDate(range.end)} 的真实新增用户折线图，不含马甲账号`}
          />
          <div className="analytics-legend" aria-hidden="true">
            <span><i className="is-green" />新增用户</span>
          </div>
        </section>
      </div>

      <div className="analytics-tables">
        <section className="analytics-table-panel" aria-labelledby="sources-title">
          <h2 id="sources-title">来源渠道</h2>
          <table>
            <thead>
              <tr>
                <th scope="col">来源渠道</th>
                <th scope="col">访问次数</th>
              </tr>
            </thead>
            <tbody>
              {SOURCE_ROWS.map((row) => (
                <tr key={row.label}>
                  <td>
                    <span>{row.label}</span>
                    <small>{row.detail}</small>
                  </td>
                  <td>{row.value}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <footer>共 2 个来源渠道</footer>
        </section>

        <section className="analytics-table-panel analytics-table-panel--entries" aria-labelledby="entries-title">
          <h2 id="entries-title">入口页面</h2>
          <table>
            <thead>
              <tr>
                <th scope="col">入口页面</th>
                <th scope="col">访问次数</th>
              </tr>
            </thead>
            <tbody>
              {ENTRY_ROWS.map((row) => (
                <tr key={row.id}>
                  <td>{row.label}</td>
                  <td>{row.value}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <footer>
            <span>共 5 个入口页面</span>
            <button type="button">查看更多 <span aria-hidden="true">›</span></button>
          </footer>
        </section>
      </div>
    </section>
  );
}

export default AnalyticsPage;
