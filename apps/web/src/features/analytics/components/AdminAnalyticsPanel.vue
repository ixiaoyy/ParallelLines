<script setup lang="ts">
import { ReloadOutlined } from "@ant-design/icons-vue";
import { LineChart } from "echarts/charts";
import { GridComponent, LegendComponent, TooltipComponent } from "echarts/components";
import * as echarts from "echarts/core";
import type { ECharts, EChartsCoreOption } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";

import { formatMetric, sourceNameLabel, sourceTypeLabel } from "@/features/analytics/model";
import type { AnalyticsMetricPoint } from "@/features/analytics/model";
import { useAnalyticsOverview } from "@/features/analytics/queries";
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";

echarts.use([LineChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer]);

const ONE_DAY_MS = 24 * 60 * 60 * 1000;
const today = new Date();
const prior = new Date(today);
prior.setDate(today.getDate() - 29);
const startDate = ref(toDateInput(prior));
const endDate = ref(toDateInput(today));
const trendChartElement = ref<HTMLDivElement | null>(null);
const growthChartElement = ref<HTMLDivElement | null>(null);
let trendChart: ECharts | null = null;
let trendResizeObserver: ResizeObserver | null = null;
let growthChart: ECharts | null = null;
let growthResizeObserver: ResizeObserver | null = null;
const dailyAverageFormatter = new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 1 });
const presetRanges = [
  { label: "7 天", days: 7 },
  { label: "30 天", days: 30 },
  { label: "90 天", days: 90 },
] as const;
const selectedRangeDays = computed(() => {
  if (!startDate.value || !endDate.value || startDate.value > endDate.value) {
    return 0;
  }
  return (
    Math.round(
      (new Date(endDate.value).getTime() - new Date(startDate.value).getTime()) / ONE_DAY_MS,
    ) + 1
  );
});
const dateRangeError = computed(() => {
  if (!startDate.value || !endDate.value) {
    return "请选择起始日期和结束日期。";
  }
  if (startDate.value > endDate.value) {
    return "起始日期不能晚于结束日期，请重新选择范围。";
  }
  return "";
});
const isDateRangeInvalid = computed(() => Boolean(dateRangeError.value));
const range = computed(() => ({ startDate: startDate.value, endDate: endDate.value }));

const overviewQuery = useAnalyticsOverview(range, computed(() => !isDateRangeInvalid.value));
const overview = computed(() => overviewQuery.data.value);
const trafficSources = computed(() => overview.value?.traffic_sources ?? []);
const entryPages = computed(() => overview.value?.entry_pages ?? []);
const rangeDayCount = computed(() => (isDateRangeInvalid.value ? 0 : selectedRangeDays.value));
const activePresetDays = computed(
  () => presetRanges.find((item) => item.days === rangeDayCount.value)?.days ?? null,
);
const totalContentItems = computed(() => {
  const totals = overview.value?.totals;
  return (totals?.topics ?? 0) + (totals?.posts ?? 0);
});
const latestPoint = computed(() => {
  const series = overview.value?.series ?? [];
  return series[series.length - 1] ?? null;
});
const latestPointLabel = computed(() => {
  const point = latestPoint.value;
  if (!point) {
    return "";
  }
  return `${formatMetric(point.page_views)} 次访问 / ${formatMetric(point.unique_visitors)} 位访客`;
});
const trendChartLabel = computed(() => {
  if (!overview.value) {
    return "每日访问量与独立访客趋势";
  }
  return `每日访问量与独立访客趋势，${overview.value.start_date} 至 ${overview.value.end_date}`;
});
const dailyRegistrationAverage = computed(() => {
  const seriesDayCount = overview.value?.series.length ?? 0;
  if (!seriesDayCount) {
    return 0;
  }
  return (overview.value?.totals.registrations ?? 0) / seriesDayCount;
});
const growthChartLabel = computed(() => {
  if (!overview.value) {
    return "每日新增用户趋势，不含马甲账号";
  }
  return `每日新增用户趋势，${overview.value.start_date} 至 ${overview.value.end_date}，区间新增 ${formatMetric(overview.value.totals.registrations)} 人，日均新增 ${dailyAverageFormatter.format(dailyRegistrationAverage.value)} 人，不含马甲账号`;
});
const summaryMetrics = computed(() => {
  const totals = overview.value?.totals;
  return [
    {
      id: "page-views",
      label: "访问量",
      value: formatMetric(totals?.page_views),
      tone: "blue",
    },
    {
      id: "unique-visitors",
      label: "独立访客",
      value: formatMetric(totals?.unique_visitors),
      tone: "green",
    },
    {
      id: "external-referrals",
      label: "引流访问",
      value: formatMetric(totals?.external_referrals),
      tone: "violet",
    },
    {
      id: "content-growth",
      label: "新增内容",
      value: formatMetric(totalContentItems.value),
      tone: "orange",
    },
  ];
});

onMounted(() => {
  void nextTick(() => {
    initTrendChart();
    initGrowthChart();
    renderTrendChart();
    renderGrowthChart();
  });
});

watch(
  () => overview.value?.series,
  () => {
    void nextTick(() => {
      renderTrendChart();
      renderGrowthChart();
    });
  },
  { deep: true },
);

watch(
  [trendChartElement, growthChartElement],
  ([trendElement, growthElement]) => {
    if (trendElement) {
      renderTrendChart();
    } else {
      disposeTrendChart();
    }
    if (growthElement) {
      renderGrowthChart();
    } else {
      disposeGrowthChart();
    }
  },
  { flush: "post" },
);

onBeforeUnmount(() => {
  disposeTrendChart();
  disposeGrowthChart();
});

// Formats a Date for native date inputs.
// Key parameter `date` is local browser time; return value is `YYYY-MM-DD`; side effect: none.
function toDateInput(date: Date): string {
  return date.toISOString().slice(0, 10);
}

// Returns the page-view value used by the trend chart.
// Key parameter `point` is one backend analytics day; return value is the visit count. Side effect: none.
function pageViews(point: AnalyticsMetricPoint): number {
  return point.page_views ?? 0;
}

// Chooses the most readable entry-page label while keeping the path available as fallback.
// Key parameters are the optional title and path; return value is display text. Side effect: none.
function entryPageLabel(title: string | null | undefined, path: string): string {
  return title || path;
}

// Applies a quick date preset ending today.
// Key parameter `days` is an inclusive day count; return value is none; side effect: updates date refs.
function applyPresetRange(days: number): void {
  const end = new Date();
  const start = new Date(end);
  start.setDate(end.getDate() - days + 1);
  startDate.value = toDateInput(start);
  endDate.value = toDateInput(end);
}

// Refreshes visible analytics queries without changing the selected range.
// Key parameters: none. Return value is none. Side effect: asks TanStack Query to refetch the overview.
function refreshDashboard(): void {
  void overviewQuery.refetch();
}

// Creates the ECharts instance for the trend line chart when its container is mounted.
// Key parameters: none. Return value is none. Side effect: initializes chart and resize observer.
function initTrendChart(): void {
  if (!trendChartElement.value || trendChart) {
    return;
  }
  trendChart = echarts.init(trendChartElement.value);
  if (typeof ResizeObserver !== "undefined") {
    trendResizeObserver = new ResizeObserver(() => trendChart?.resize());
    trendResizeObserver.observe(trendChartElement.value);
  }
}

// Creates the ECharts instance for the user-growth chart when its container is mounted.
// Key parameters: none. Return value is none. Side effect: initializes the chart and resize observer.
function initGrowthChart(): void {
  if (!growthChartElement.value || growthChart) {
    return;
  }
  growthChart = echarts.init(growthChartElement.value);
  if (typeof ResizeObserver !== "undefined") {
    growthResizeObserver = new ResizeObserver(() => growthChart?.resize());
    growthResizeObserver.observe(growthChartElement.value);
  }
}

// Releases the chart instance and observer before Vue removes the component.
// Key parameters: none. Return value is none. Side effect: disconnects observer and disposes ECharts.
function disposeTrendChart(): void {
  trendResizeObserver?.disconnect();
  trendResizeObserver = null;
  trendChart?.dispose();
  trendChart = null;
}

// Releases the user-growth chart instance and observer when its container is removed.
// Key parameters: none. Return value is none. Side effect: disconnects the observer and disposes ECharts.
function disposeGrowthChart(): void {
  growthResizeObserver?.disconnect();
  growthResizeObserver = null;
  growthChart?.dispose();
  growthChart = null;
}

// Renders the latest analytics series into the ECharts line chart.
// Key parameters: none. Return value is none. Side effect: updates the chart instance.
function renderTrendChart(): void {
  if (!overview.value || !trendChartElement.value) {
    return;
  }
  initTrendChart();
  trendChart?.setOption(
    buildTrendChartOption(overview.value.series ?? [], trendChartElement.value),
    { notMerge: true },
  );
}

// Renders daily non-persona registrations into the user-growth chart.
// Key parameters: none. Return value is none. Side effect: updates the growth chart instance.
function renderGrowthChart(): void {
  if (!overview.value || !growthChartElement.value) {
    return;
  }
  initGrowthChart();
  growthChart?.setOption(
    buildGrowthChartOption(overview.value.series ?? [], growthChartElement.value),
    { notMerge: true },
  );
}

// Builds the localized line-chart option from backend metric points and current CSS tokens.
// Key parameters are the backend `points` and chart `element`. Return value is ECharts config. Side effect: none.
function buildTrendChartOption(
  points: AnalyticsMetricPoint[],
  element: HTMLElement,
): EChartsCoreOption {
  const primary = readCssVar(element, "--primary", "#409eff");
  const visitor = readCssVar(element, "--accent-geek", "#10b981");
  const text = readCssVar(element, "--text", "#475569");
  const muted = readCssVar(element, "--muted", "#94a3b8");
  const border = readCssVar(element, "--border", "#e2e8f0");
  const labels = points.map((point) => point.day.slice(5).replace("-", "/"));

  return {
    animationDuration: 180,
    color: [primary, visitor],
    grid: { bottom: 42, containLabel: true, left: 8, right: 14, top: 22 },
    legend: {
      bottom: 0,
      data: ["访问量", "独立访客"],
      icon: "roundRect",
      itemHeight: 6,
      itemWidth: 12,
      left: 0,
      textStyle: { color: muted, fontSize: 12 },
    },
    series: [
      {
        areaStyle: { color: primary, opacity: 0.08 },
        data: points.map(pageViews),
        emphasis: { focus: "series" },
        itemStyle: { color: primary },
        lineStyle: { color: primary, width: 3 },
        name: "访问量",
        showSymbol: points.length <= 14,
        smooth: true,
        symbol: "circle",
        symbolSize: 6,
        type: "line",
      },
      {
        data: points.map((point) => point.unique_visitors ?? 0),
        emphasis: { focus: "series" },
        itemStyle: { color: visitor },
        lineStyle: { color: visitor, width: 2 },
        name: "独立访客",
        showSymbol: points.length <= 14,
        smooth: true,
        symbol: "circle",
        symbolSize: 5,
        type: "line",
      },
    ],
    textStyle: { color: text, fontFamily: "inherit" },
    tooltip: {
      confine: true,
      formatter: formatChartTooltip,
      trigger: "axis",
    },
    xAxis: {
      axisLabel: { color: muted, fontSize: 11, hideOverlap: true },
      axisLine: { lineStyle: { color: border } },
      axisTick: { show: false },
      boundaryGap: false,
      data: labels,
      type: "category",
    },
    yAxis: {
      axisLabel: { color: muted, formatter: (value: number) => formatMetric(value) },
      min: 0,
      minInterval: 1,
      splitLine: { lineStyle: { color: border, opacity: 0.6 } },
      type: "value",
    },
  };
}

// Builds the localized single-series option for daily non-persona registrations.
// Key parameters are backend metric `points` and the chart `element`. Return value is ECharts config. Side effect: none.
function buildGrowthChartOption(
  points: AnalyticsMetricPoint[],
  element: HTMLElement,
): EChartsCoreOption {
  const growth = readCssVar(element, "--accent-violet", "#6366f1");
  const text = readCssVar(element, "--text", "#475569");
  const muted = readCssVar(element, "--muted", "#94a3b8");
  const border = readCssVar(element, "--border", "#e2e8f0");
  const labels = points.map((point) => point.day.slice(5).replace("-", "/"));

  return {
    animationDuration: 180,
    color: [growth],
    grid: { bottom: 26, containLabel: true, left: 8, right: 14, top: 14 },
    series: [
      {
        areaStyle: { color: growth, opacity: 0.08 },
        data: points.map((point) => point.registrations ?? 0),
        emphasis: { focus: "series" },
        itemStyle: { color: growth },
        lineStyle: { color: growth, width: 3 },
        name: "新增用户",
        showSymbol: points.length <= 14,
        smooth: true,
        symbol: "circle",
        symbolSize: 6,
        type: "line",
      },
    ],
    textStyle: { color: text, fontFamily: "inherit" },
    tooltip: {
      confine: true,
      formatter: formatChartTooltip,
      trigger: "axis",
    },
    xAxis: {
      axisLabel: { color: muted, fontSize: 11, hideOverlap: true },
      axisLine: { lineStyle: { color: border } },
      axisTick: { show: false },
      boundaryGap: false,
      data: labels,
      type: "category",
    },
    yAxis: {
      axisLabel: { color: muted, formatter: (value: number) => formatMetric(value) },
      min: 0,
      minInterval: 1,
      splitLine: { lineStyle: { color: border, opacity: 0.6 } },
      type: "value",
    },
  };
}

// Reads a CSS custom property from the chart host with a token-safe fallback.
// Key parameters are the DOM `element`, CSS variable name, and fallback. Return value is a color/string. Side effect: none.
function readCssVar(element: HTMLElement, variableName: string, fallback: string): string {
  return getComputedStyle(element).getPropertyValue(variableName).trim() || fallback;
}

interface ChartTooltipItem {
  axisValueLabel?: string;
  data?: unknown;
  marker?: string;
  seriesName?: string;
}

// Narrows ECharts tooltip callback values to the object shape used by axis tooltips.
// Key parameter `value` is the callback payload. Return value reports whether it is usable. Side effect: none.
function isChartTooltipItem(value: unknown): value is ChartTooltipItem {
  return typeof value === "object" && value !== null;
}

// Formats the ECharts tooltip in Chinese without exposing PV/UV terminology.
// Key parameter `params` is the ECharts tooltip payload. Return value is HTML text for the library tooltip. Side effect: none.
function formatChartTooltip(params: unknown): string {
  const items = (Array.isArray(params) ? params : [params]).filter(isChartTooltipItem);
  const title = items[0]?.axisValueLabel ? String(items[0].axisValueLabel) : "";
  const rows = items.map((item) => {
    const numericValue = typeof item.data === "number" ? item.data : Number(item.data);
    const value = Number.isFinite(numericValue)
      ? formatMetric(numericValue)
      : String(item.data ?? "—");
    const unit =
      item.seriesName === "独立访客" ? " 位" : item.seriesName === "新增用户" ? " 人" : " 次";
    return `${item.marker ?? ""}${item.seriesName ?? ""}: ${value}${unit}`;
  });
  return [title, ...rows].filter(Boolean).join("<br/>");
}

</script>

<template>
  <UiCard class="admin-analytics-panel">
    <section class="analytics-hero" aria-labelledby="analytics-title">
      <div class="analytics-hero__copy">
        <h2 id="analytics-title">访问看板</h2>
      </div>
      <div class="analytics-hero__aside">
        <span class="range-chip">{{ rangeDayCount || "—" }} 天</span>
        <UiButton tone="subtle" :disabled="isDateRangeInvalid" @click="refreshDashboard">
          <template #icon><ReloadOutlined /></template>
          刷新
        </UiButton>
      </div>
    </section>

    <section class="analytics-toolbar" aria-label="报表日期范围">
      <div class="range-presets" aria-label="快速日期范围">
        <button
          v-for="preset in presetRanges"
          :key="preset.days"
          type="button"
          :class="{ active: activePresetDays === preset.days }"
          @click="applyPresetRange(preset.days)"
        >
          {{ preset.label }}
        </button>
      </div>
      <div class="date-fields">
        <label>
          <span>起始日期</span>
          <input v-model="startDate" type="date" />
        </label>
        <label>
          <span>结束日期</span>
          <input v-model="endDate" type="date" />
        </label>
      </div>
    </section>

    <div v-if="isDateRangeInvalid" class="analytics-state analytics-state--error" role="alert">
      {{ dateRangeError }}
    </div>
    <div v-else-if="overviewQuery.isLoading.value" class="analytics-state" role="status">
      正在计算访问与运营指标…
    </div>
    <div v-else-if="overviewQuery.isError.value" class="analytics-state analytics-state--error" role="alert">
      报表暂时不可用，请确认当前账号具备管理员权限。
    </div>
    <template v-else-if="overview">
      <section class="metric-grid" aria-label="访问核心指标">
        <article v-for="metric in summaryMetrics" :key="metric.id" :class="`metric-card metric-card--${metric.tone}`">
          <span>{{ metric.label }}</span>
          <strong>{{ metric.value }}</strong>
        </article>
      </section>

      <section class="analytics-main-grid" aria-label="访问趋势与内容榜单">
        <article class="trend-panel">
          <div class="section-heading">
            <div>
              <strong>站点访问趋势</strong>
              <span>{{ overview.start_date }} → {{ overview.end_date }}</span>
            </div>
            <small v-if="latestPointLabel">最新 {{ latestPointLabel }}</small>
          </div>
          <div ref="trendChartElement" class="trend-chart" role="img" :aria-label="trendChartLabel"></div>
        </article>

        <article class="top-topics-panel">
          <div class="section-heading">
            <div>
              <strong>来源渠道</strong>
            </div>
          </div>
          <ol v-if="trafficSources.length" class="topic-rank-list">
            <li
              v-for="source in trafficSources"
              :key="`${source.source_type}:${source.source_name}`"
            >
              <span class="rank-title">{{ sourceNameLabel(source.source_name) }}</span>
              <span class="rank-board">
                {{ sourceTypeLabel(source.source_type) }} · {{ formatMetric(source.unique_visitors) }} 位访客
              </span>
              <strong>{{ formatMetric(source.visit_count) }} 次访问</strong>
            </li>
          </ol>
          <p v-else class="analytics-state">当前范围内暂无访问来源。</p>
        </article>
      </section>

      <section class="user-growth-panel" aria-labelledby="user-growth-title">
        <div class="section-heading">
          <div>
            <strong id="user-growth-title">用户增长</strong>
            <span>{{ overview.start_date }} → {{ overview.end_date }} · 不含马甲账号</span>
          </div>
        </div>
        <div class="user-growth-layout">
          <div class="user-growth-summary" aria-label="用户增长汇总">
            <div>
              <span>区间新增</span>
              <strong>{{ formatMetric(overview.totals.registrations) }}</strong>
              <small>人</small>
            </div>
            <div>
              <span>日均新增</span>
              <strong>{{ dailyAverageFormatter.format(dailyRegistrationAverage) }}</strong>
              <small>人</small>
            </div>
          </div>
          <div
            ref="growthChartElement"
            class="growth-chart"
            role="img"
            :aria-label="growthChartLabel"
          ></div>
        </div>
      </section>

      <section class="analytics-list-grid" aria-label="入口页统计">
        <article>
          <div class="section-heading">
            <strong>入口页</strong>
          </div>
          <ol v-if="entryPages.length">
            <li v-for="page in entryPages" :key="page.path">
              <span :title="page.path">{{ entryPageLabel(page.title, page.path) }}</span>
              <strong>{{ formatMetric(page.visit_count) }} 次访问</strong>
            </li>
          </ol>
          <p v-else class="analytics-state">暂无入口页数据。</p>
        </article>
      </section>
    </template>
  </UiCard>
</template>

<style scoped lang="scss" src="./AdminAnalyticsPanel.scss"></style>
