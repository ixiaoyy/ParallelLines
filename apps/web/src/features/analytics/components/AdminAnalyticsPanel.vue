<script setup lang="ts">
import {
  BranchesOutlined,
  DatabaseOutlined,
  DownloadOutlined,
  FileTextOutlined,
  ReloadOutlined,
  RiseOutlined,
  UserAddOutlined,
} from "@ant-design/icons-vue";
import { LineChart } from "echarts/charts";
import { GridComponent, LegendComponent, TooltipComponent } from "echarts/components";
import * as echarts from "echarts/core";
import type { ECharts, EChartsCoreOption } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";

import {
  formatMetric,
  reportCell,
  sourceNameLabel,
  sourceTypeLabel,
} from "@/features/analytics/model";
import type {
  AnalyticsMetricPoint,
  DataExplorerReportSummary,
} from "@/features/analytics/model";
import {
  useAnalyticsOverview,
  useDataExplorerReport,
  useDataExplorerReports,
  useExportDataExplorerReport,
} from "@/features/analytics/queries";
import UiButton from "@/shared/ui/Button.vue";

echarts.use([LineChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer]);

const ONE_DAY_MS = 24 * 60 * 60 * 1000;
const MAX_ANALYTICS_RANGE_DAYS = 366;
const today = new Date();
const prior = new Date(today);
prior.setDate(today.getDate() - 29);
const startDate = ref(toDateInput(prior));
const endDate = ref(toDateInput(today));
const selectedReportId = ref("");
const dataExplorerOpen = ref(false);
const exportFeedback = ref("");
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
      (new Date(`${endDate.value}T00:00:00`).getTime() -
        new Date(`${startDate.value}T00:00:00`).getTime()) /
        ONE_DAY_MS,
    ) + 1
  );
});
const dateRangeError = computed(() => {
  if (!startDate.value || !endDate.value) {
    return "请选择开始日期和结束日期。";
  }
  if (startDate.value > endDate.value) {
    return "开始日期不能晚于结束日期，请重新选择范围。";
  }
  if (selectedRangeDays.value > MAX_ANALYTICS_RANGE_DAYS) {
    return `统计范围最多为 ${MAX_ANALYTICS_RANGE_DAYS} 天，请缩短日期范围。`;
  }
  return "";
});
const isDateRangeInvalid = computed(() => Boolean(dateRangeError.value));
const range = computed(() => ({ startDate: startDate.value, endDate: endDate.value }));
const rangeDayCount = computed(() => (isDateRangeInvalid.value ? 0 : selectedRangeDays.value));
const activePresetDays = computed(
  () => presetRanges.find((item) => item.days === rangeDayCount.value)?.days ?? null,
);

const overviewQuery = useAnalyticsOverview(range, computed(() => !isDateRangeInvalid.value));
const overview = computed(() => overviewQuery.data.value);
const trafficSources = computed(() => overview.value?.traffic_sources ?? []);
const entryPages = computed(() => overview.value?.entry_pages ?? []);
const totalContentItems = computed(() => {
  const totals = overview.value?.totals;
  return (totals?.topics ?? 0) + (totals?.posts ?? 0);
});
const dailyRegistrationAverage = computed(() => {
  const seriesDayCount = overview.value?.series.length ?? 0;
  if (!seriesDayCount) {
    return 0;
  }
  return (overview.value?.totals.registrations ?? 0) / seriesDayCount;
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
      tone: "teal",
    },
    {
      id: "registrations",
      label: "区间新增用户",
      value: formatMetric(totals?.registrations),
      note: "不含马甲账号",
      icon: UserAddOutlined,
      tone: "green",
    },
    {
      id: "daily-registration-average",
      label: "日均新增",
      value: dailyAverageFormatter.format(dailyRegistrationAverage.value),
      icon: RiseOutlined,
      tone: "violet",
    },
    {
      id: "external-referrals",
      label: "引流访问",
      value: formatMetric(totals?.external_referrals),
      icon: BranchesOutlined,
      tone: "blue",
    },
    {
      id: "content-growth",
      label: "新增内容",
      value: formatMetric(totalContentItems.value),
      icon: FileTextOutlined,
      tone: "orange",
    },
  ];
});
const trendChartLabel = computed(() => {
  if (!overview.value) {
    return "每日访问量与独立访客趋势";
  }
  return `每日访问量与独立访客趋势，${overview.value.start_date} 至 ${overview.value.end_date}`;
});
const growthChartLabel = computed(() => {
  if (!overview.value) {
    return "每日新增用户趋势，不含马甲账号";
  }
  return `每日新增用户趋势，${overview.value.start_date} 至 ${overview.value.end_date}，区间新增 ${formatMetric(overview.value.totals.registrations)} 人，日均新增 ${dailyAverageFormatter.format(dailyRegistrationAverage.value)} 人，不含马甲账号`;
});

const reportsQuery = useDataExplorerReports(dataExplorerOpen);
const reports = computed(() => reportsQuery.data.value ?? []);
const selectedReport = computed<DataExplorerReportSummary | null>(
  () => reports.value.find((item) => item.id === selectedReportId.value) ?? null,
);
const reportQuery = useDataExplorerReport(
  selectedReportId,
  range,
  computed(
    () =>
      dataExplorerOpen.value && Boolean(selectedReportId.value) && !isDateRangeInvalid.value,
  ),
);
const report = computed(() => reportQuery.data.value);
const reportColumns = computed(() => report.value?.columns ?? []);
const reportRows = computed(() => report.value?.rows ?? []);
const exportReport = useExportDataExplorerReport();

watch(
  reports,
  (items) => {
    if (!items.some((item) => item.id === selectedReportId.value)) {
      selectedReportId.value = items[0]?.id ?? "";
    }
  },
  { immediate: true },
);

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

// Formats a local Date for native date inputs without UTC day shifts.
// Key parameter `date` is browser local time; return value is `YYYY-MM-DD`. Side effect: none.
function toDateInput(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

// Returns the page-view value used by the access trend chart.
// Key parameter `point` is one backend analytics day; return value is the visit count. Side effect: none.
function pageViews(point: AnalyticsMetricPoint): number {
  return point.page_views ?? 0;
}

// Chooses a readable entry-page title while retaining the backend path as fallback.
// Key parameters are the optional title and path; return value is display text. Side effect: none.
function entryPageLabel(title: string | null | undefined, path: string): string {
  return title || path;
}

// Applies an inclusive quick range ending on the user's local current day.
// Key parameter `days` is an inclusive day count; return value is none. Side effect: updates date refs.
function applyPresetRange(days: number): void {
  const end = new Date();
  const start = new Date(end);
  start.setDate(end.getDate() - days + 1);
  startDate.value = toDateInput(start);
  endDate.value = toDateInput(end);
}

// Refreshes the overview and the currently visible preset report.
// Key parameters: none. Return value is none. Side effect: refetches active TanStack queries.
function refreshDashboard(): void {
  void overviewQuery.refetch();
  if (dataExplorerOpen.value && selectedReportId.value) {
    void reportQuery.refetch();
  }
}

// Opens or closes Data Explorer while preserving its selected backend report.
// Key parameters: none. Return value is none. Side effect: toggles the disclosure and enables its queries.
function toggleDataExplorer(): void {
  dataExplorerOpen.value = !dataExplorerOpen.value;
  exportFeedback.value = "";
}

// Switches the active backend-owned Data Explorer report preset.
// Key parameter `reportId` is a backend report identifier; return value is none. Side effect: updates query state.
function selectReport(reportId: string): void {
  selectedReportId.value = reportId;
  exportFeedback.value = "";
}

// Downloads the selected report through the authenticated CSV endpoint.
// Key parameters: none. Return value is none. Side effect: creates a temporary download link and triggers a browser download.
function exportCsv(): void {
  if (!selectedReportId.value || isDateRangeInvalid.value) {
    return;
  }
  exportFeedback.value = "";
  exportReport.mutate(
    { reportId: selectedReportId.value, params: range.value },
    {
      onError: () => {
        exportFeedback.value = "CSV 导出失败，请稍后重试。";
      },
      onSuccess: (blob) => {
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = `${selectedReportId.value}.csv`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);
        exportFeedback.value = "CSV 已开始下载，操作已记录到审计日志。";
      },
    },
  );
}

// Creates the ECharts instance for the access trend when its container is mounted.
// Key parameters: none. Return value is none. Side effect: initializes a chart and resize observer.
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

// Creates the ECharts instance for real-user growth when its container is mounted.
// Key parameters: none. Return value is none. Side effect: initializes a chart and resize observer.
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

// Releases the access trend chart and observer before Vue removes the component.
// Key parameters: none. Return value is none. Side effect: disconnects and disposes chart resources.
function disposeTrendChart(): void {
  trendResizeObserver?.disconnect();
  trendResizeObserver = null;
  trendChart?.dispose();
  trendChart = null;
}

// Releases the real-user growth chart and observer before Vue removes the component.
// Key parameters: none. Return value is none. Side effect: disconnects and disposes chart resources.
function disposeGrowthChart(): void {
  growthResizeObserver?.disconnect();
  growthResizeObserver = null;
  growthChart?.dispose();
  growthChart = null;
}

// Renders the latest backend series into the access trend chart.
// Key parameters: none. Return value is none. Side effect: updates the ECharts instance.
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

// Renders backend-filtered non-persona registrations into the growth chart.
// Key parameters: none. Return value is none. Side effect: updates the ECharts instance.
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

// Reports whether the browser requests reduced motion for chart transitions.
// Key parameters: none. Return value is true when motion should be minimized. Side effect: reads media preference.
function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

// Builds the localized access line-chart option from backend points and design tokens.
// Key parameters are backend `points` and chart `element`; return value is ECharts config. Side effect: reads CSS tokens.
function buildTrendChartOption(
  points: AnalyticsMetricPoint[],
  element: HTMLElement,
): EChartsCoreOption {
  const primary = readCssVar(element, "--primary", "#409eff");
  const visitor = readCssVar(element, "--accent-geek", "#10b981");
  const text = readCssVar(element, "--text", "#475569");
  const muted = readCssVar(element, "--analytics-muted", "#64748b");
  const border = readCssVar(element, "--border", "#e2e8f0");
  const labels = points.map((point) => point.day.slice(5).replace("-", "/"));

  return {
    animation: !prefersReducedMotion(),
    animationDuration: 180,
    color: [primary, visitor],
    grid: { bottom: 42, containLabel: true, left: 8, right: 14, top: 16 },
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
        data: points.map(pageViews),
        emphasis: { focus: "series" },
        itemStyle: { color: primary },
        lineStyle: { color: primary, width: 2.5 },
        name: "访问量",
        showSymbol: points.length <= 14,
        smooth: 0.35,
        symbol: "circle",
        symbolSize: 5,
        type: "line",
      },
      {
        data: points.map((point) => point.unique_visitors ?? 0),
        emphasis: { focus: "series" },
        itemStyle: { color: visitor },
        lineStyle: { color: visitor, width: 2 },
        name: "独立访客",
        showSymbol: points.length <= 14,
        smooth: 0.35,
        symbol: "circle",
        symbolSize: 5,
        type: "line",
      },
    ],
    textStyle: { color: text, fontFamily: "inherit" },
    tooltip: { confine: true, formatter: formatChartTooltip, trigger: "axis" },
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
      splitLine: { lineStyle: { color: border, opacity: 0.75 } },
      type: "value",
    },
  };
}

// Builds the localized real-user growth chart from backend-filtered registration points.
// Key parameters are backend `points` and chart `element`; return value is ECharts config. Side effect: reads CSS tokens.
function buildGrowthChartOption(
  points: AnalyticsMetricPoint[],
  element: HTMLElement,
): EChartsCoreOption {
  const growth = readCssVar(element, "--accent-geek", "#10b981");
  const text = readCssVar(element, "--text", "#475569");
  const muted = readCssVar(element, "--analytics-muted", "#64748b");
  const border = readCssVar(element, "--border", "#e2e8f0");
  const labels = points.map((point) => point.day.slice(5).replace("-", "/"));

  return {
    animation: !prefersReducedMotion(),
    animationDuration: 180,
    color: [growth],
    grid: { bottom: 42, containLabel: true, left: 8, right: 14, top: 16 },
    legend: {
      bottom: 0,
      data: ["新增用户"],
      icon: "roundRect",
      itemHeight: 6,
      itemWidth: 12,
      left: 0,
      textStyle: { color: muted, fontSize: 12 },
    },
    series: [
      {
        data: points.map((point) => point.registrations ?? 0),
        emphasis: { focus: "series" },
        itemStyle: { color: growth },
        lineStyle: { color: growth, width: 2.5 },
        name: "新增用户",
        showSymbol: points.length <= 14,
        smooth: 0.35,
        symbol: "circle",
        symbolSize: 5,
        type: "line",
      },
    ],
    textStyle: { color: text, fontFamily: "inherit" },
    tooltip: { confine: true, formatter: formatChartTooltip, trigger: "axis" },
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
      splitLine: { lineStyle: { color: border, opacity: 0.75 } },
      type: "value",
    },
  };
}

// Reads a CSS custom property from the chart host with a token-safe fallback.
// Key parameters are the DOM `element`, variable name, and fallback; return value is a CSS value. Side effect: reads computed style.
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
// Key parameter `value` is the callback payload; return value reports whether it is usable. Side effect: none.
function isChartTooltipItem(value: unknown): value is ChartTooltipItem {
  return typeof value === "object" && value !== null;
}

// Formats numeric ECharts tooltip values in Chinese without exposing internal PV/UV terms.
// Key parameter `params` is the ECharts payload; return value is library tooltip HTML using fixed labels. Side effect: none.
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
  <section class="admin-analytics-panel" aria-labelledby="analytics-title">
    <header class="analytics-page-header">
      <div>
        <h1 id="analytics-title">访问与用户增长</h1>
        <p>查看所选日期范围内的访问表现与真实用户增长。</p>
      </div>
      <div class="analytics-header-actions">
        <UiButton
          tone="ghost"
          :disabled="isDateRangeInvalid || overviewQuery.isFetching.value"
          :aria-label="overviewQuery.isFetching.value ? '正在刷新访问与用户增长数据' : '刷新访问与用户增长数据'"
          :title="overviewQuery.isFetching.value ? '正在刷新访问与用户增长数据' : '刷新访问与用户增长数据'"
          @click="refreshDashboard"
        >
          <template #icon>
            <ReloadOutlined :class="{ 'is-spinning': overviewQuery.isFetching.value }" aria-hidden="true" />
          </template>
          {{ overviewQuery.isFetching.value ? "刷新中" : "刷新" }}
        </UiButton>
      </div>
    </header>

    <section class="analytics-toolbar" aria-label="统计日期范围">
      <div class="range-presets" aria-label="快速日期范围">
        <button
          v-for="preset in presetRanges"
          :key="preset.days"
          type="button"
          :class="{ active: activePresetDays === preset.days }"
          :aria-pressed="activePresetDays === preset.days"
          @click="applyPresetRange(preset.days)"
        >
          {{ preset.label }}
        </button>
      </div>
      <span class="toolbar-divider" aria-hidden="true"></span>
      <div class="date-fields">
        <label>
          <span>开始日期</span>
          <input v-model="startDate" type="date" />
        </label>
        <label>
          <span>结束日期</span>
          <input v-model="endDate" type="date" />
        </label>
      </div>
    </section>

    <div v-if="isDateRangeInvalid" class="analytics-state analytics-state--error" role="alert">
      <strong>日期范围无效</strong>
      <span>{{ dateRangeError }}</span>
    </div>

    <section v-else-if="overviewQuery.isLoading.value" class="analytics-loading" role="status">
      <span class="sr-only">正在计算访问与运营指标…</span>
      <div class="loading-metrics" aria-hidden="true">
        <i v-for="index in 6" :key="index"></i>
      </div>
      <div class="loading-charts" aria-hidden="true"><i></i><i></i></div>
    </section>

    <div v-else-if="overviewQuery.isError.value" class="analytics-state analytics-state--error" role="alert">
      <div>
        <strong>访问报表暂时不可用</strong>
        <span>请确认当前账号具备管理员权限，或稍后重新加载。</span>
      </div>
      <UiButton tone="subtle" @click="refreshDashboard">重新加载</UiButton>
    </div>

    <template v-else-if="overview">
      <section class="metric-strip" aria-label="核心指标">
        <article
          v-for="metric in summaryMetrics"
          :key="metric.id"
          :class="`metric-item metric-item--${metric.tone}`"
        >
          <span>{{ metric.label }}</span>
          <div class="metric-value">
            <strong>{{ metric.value }}</strong>
            <small v-if="metric.note">{{ metric.note }}</small>
            <component :is="metric.icon" v-if="metric.icon" class="metric-icon" aria-hidden="true" />
          </div>
        </article>
      </section>

      <section class="analytics-chart-grid" aria-label="访问与用户增长趋势">
        <article class="analytics-chart-panel">
          <div class="section-heading">
            <div>
              <h2>站点访问趋势</h2>
              <span>{{ overview.start_date }} → {{ overview.end_date }}</span>
            </div>
          </div>
          <div
            ref="trendChartElement"
            class="analytics-chart"
            role="img"
            :aria-label="trendChartLabel"
          ></div>
        </article>

        <article class="analytics-chart-panel analytics-chart-panel--growth">
          <div class="section-heading">
            <div>
              <h2>用户增长趋势</h2>
              <span>真实注册用户 · 不含马甲账号</span>
            </div>
          </div>
          <div
            ref="growthChartElement"
            class="analytics-chart"
            role="img"
            :aria-label="growthChartLabel"
          ></div>
        </article>
      </section>

      <section class="analytics-table-grid" aria-label="来源与入口页统计">
        <article class="analytics-table-panel">
          <div class="section-heading">
            <h2>来源渠道</h2>
          </div>
          <div class="analytics-table-wrap">
            <table>
              <thead>
                <tr><th scope="col">来源渠道</th><th scope="col">访问次数</th></tr>
              </thead>
              <tbody v-if="trafficSources.length">
                <tr
                  v-for="source in trafficSources"
                  :key="`${source.source_type}:${source.source_name}`"
                >
                  <td>
                    <span>{{ sourceNameLabel(source.source_name) }}</span>
                    <small>{{ sourceTypeLabel(source.source_type) }} · {{ formatMetric(source.unique_visitors) }} 位访客</small>
                  </td>
                  <td>{{ formatMetric(source.visit_count) }}</td>
                </tr>
              </tbody>
            </table>
            <p v-if="!trafficSources.length" class="table-empty">当前范围内暂无访问来源。</p>
          </div>
          <footer>共 {{ trafficSources.length }} 个来源渠道</footer>
        </article>

        <article class="analytics-table-panel analytics-table-panel--entries">
          <div class="section-heading">
            <h2>入口页面</h2>
          </div>
          <div class="analytics-table-wrap">
            <table>
              <thead>
                <tr><th scope="col">入口页面</th><th scope="col">访问次数</th></tr>
              </thead>
              <tbody v-if="entryPages.length">
                <tr v-for="page in entryPages" :key="page.path">
                  <td :title="page.path">{{ entryPageLabel(page.title, page.path) }}</td>
                  <td>{{ formatMetric(page.visit_count) }}</td>
                </tr>
              </tbody>
            </table>
            <p v-if="!entryPages.length" class="table-empty">当前范围内暂无入口页数据。</p>
          </div>
          <footer>共 {{ entryPages.length }} 个入口页面</footer>
        </article>
      </section>
    </template>

    <section class="data-explorer" aria-labelledby="data-explorer-title">
      <div class="data-explorer-heading">
        <div>
          <DatabaseOutlined aria-hidden="true" />
          <div>
            <h2 id="data-explorer-title">数据探索</h2>
            <p>运行后端预设的安全报表；CSV 导出会写入审计日志。</p>
          </div>
        </div>
        <UiButton
          tone="ghost"
          :aria-expanded="dataExplorerOpen"
          aria-controls="data-explorer-content"
          @click="toggleDataExplorer"
        >
          {{ dataExplorerOpen ? "收起" : "打开预设报表" }}
        </UiButton>
      </div>

      <div v-if="dataExplorerOpen" id="data-explorer-content" class="data-explorer-content">
        <div v-if="reportsQuery.isLoading.value" class="analytics-state" role="status">
          正在读取预设报表…
        </div>
        <div v-else-if="reportsQuery.isError.value" class="analytics-state analytics-state--error" role="alert">
          <span>预设报表读取失败，请稍后重试。</span>
          <UiButton tone="subtle" @click="reportsQuery.refetch()">重新加载</UiButton>
        </div>
        <template v-else>
          <div class="report-toolbar">
            <div class="report-tabs" aria-label="预设报表">
              <button
                v-for="item in reports"
                :key="item.id"
                type="button"
                :aria-pressed="item.id === selectedReportId"
                :class="{ active: item.id === selectedReportId }"
                @click="selectReport(item.id)"
              >
                {{ item.name }}
              </button>
            </div>
            <UiButton
              tone="subtle"
              :disabled="!selectedReportId || isDateRangeInvalid || exportReport.isPending.value"
              @click="exportCsv"
            >
              <template #icon><DownloadOutlined /></template>
              {{ exportReport.isPending.value ? "导出中" : "导出 CSV" }}
            </UiButton>
          </div>

          <p v-if="selectedReport" class="report-description">{{ selectedReport.description }}</p>
          <p v-if="exportFeedback" class="export-feedback" aria-live="polite">{{ exportFeedback }}</p>
          <div v-if="reportQuery.isLoading.value" class="analytics-state" role="status">
            正在运行报表…
          </div>
          <div v-else-if="reportQuery.isError.value" class="analytics-state analytics-state--error" role="alert">
            报表运行失败，请检查日期范围后重试。
          </div>
          <div v-else-if="report" class="report-table-wrap">
            <table class="report-table">
              <thead>
                <tr><th v-for="column in reportColumns" :key="column" scope="col">{{ column }}</th></tr>
              </thead>
              <tbody>
                <tr v-for="(row, index) in reportRows" :key="index">
                  <td v-for="column in reportColumns" :key="column">{{ reportCell(row[column]) }}</td>
                </tr>
                <tr v-if="!reportRows.length">
                  <td :colspan="Math.max(1, reportColumns.length)" class="report-empty">当前范围内没有结果。</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-else-if="!reports.length" class="table-empty">暂无可用的预设报表。</p>
        </template>
      </div>
    </section>
  </section>
</template>

<style scoped lang="scss" src="./AdminAnalyticsPanel.scss"></style>
