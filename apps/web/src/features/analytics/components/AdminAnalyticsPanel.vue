<script setup lang="ts">
import { DownloadOutlined, ReloadOutlined } from "@ant-design/icons-vue";
import { computed, ref, watch } from "vue";

import { formatMetric, reportCell } from "@/features/analytics/model";
import type { AnalyticsMetricPoint } from "@/features/analytics/model";
import {
  useAnalyticsOverview,
  useDataExplorerReport,
  useDataExplorerReports,
  useExportDataExplorerReport,
} from "@/features/analytics/queries";
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";

const ONE_DAY_MS = 24 * 60 * 60 * 1000;
const today = new Date();
const prior = new Date(today);
prior.setDate(today.getDate() - 29);
const startDate = ref(toDateInput(prior));
const endDate = ref(toDateInput(today));
const selectedReportId = ref("");
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
const reportsQuery = useDataExplorerReports();
const reports = computed(() => reportsQuery.data.value ?? []);
const reportQuery = useDataExplorerReport(
  selectedReportId,
  range,
  computed(() => Boolean(selectedReportId.value) && !isDateRangeInvalid.value),
);
const report = computed(() => reportQuery.data.value);
const reportColumns = computed(() => report.value?.columns ?? []);
const reportRows = computed(() => report.value?.rows ?? []);
const exportReport = useExportDataExplorerReport();
const maxPageViews = computed(() =>
  Math.max(1, ...(overview.value?.series ?? []).map((point) => pageViews(point))),
);
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
const summaryMetrics = computed(() => {
  const totals = overview.value?.totals;
  return [
    {
      id: "page-views",
      label: "PV",
      value: formatMetric(totals?.page_views),
      tone: "blue",
    },
    {
      id: "unique-visitors",
      label: "UV",
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

watch(
  reports,
  (items) => {
    if (!selectedReportId.value && items[0]) {
      selectedReportId.value = items[0].id;
    }
  },
  { immediate: true },
);

// Formats a Date for native date inputs.
// Key parameter `date` is local browser time; return value is `YYYY-MM-DD`; side effect: none.
function toDateInput(date: Date): string {
  return date.toISOString().slice(0, 10);
}

// Returns the page-view value used by the compact trend bars.
// Key parameter `point` is one backend analytics day; return value is PV count; side effect: none.
function pageViews(point: AnalyticsMetricPoint): number {
  return point.page_views ?? 0;
}

// Converts backend source identifiers into compact Chinese labels for the dashboard.
// Key parameter `sourceType` is the normalized backend source type; return value is display text.
// Side effect: none.
function sourceTypeLabel(sourceType: string): string {
  const labels: Record<string, string> = {
    campaign: "活动",
    direct: "直接",
    internal: "站内",
    referral: "外链",
    search: "搜索",
    social: "社媒",
  };
  return labels[sourceType] ?? sourceType;
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
// Key parameters: none. Return value is none; side effect: asks TanStack Query to refetch active reports.
function refreshDashboard(): void {
  void overviewQuery.refetch();
  if (selectedReportId.value) {
    void reportQuery.refetch();
  }
}

// Downloads the selected Data Explorer report with authenticated headers.
// Key parameters: none. Return value is none; side effect: creates and clicks a temporary download link.
function exportCsv(): void {
  if (!selectedReportId.value) {
    return;
  }
  exportReport.mutate(
    { reportId: selectedReportId.value, params: range.value },
    {
      onSuccess: (blob) => {
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = `${selectedReportId.value}.csv`;
        link.click();
        URL.revokeObjectURL(url);
      },
    },
  );
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
            <small v-if="latestPoint">
              最新 {{ formatMetric(pageViews(latestPoint)) }} PV
            </small>
          </div>
          <div class="trend-bars" role="img" aria-label="每日站点 PV 趋势">
            <span
              v-for="point in overview.series"
              :key="point.day"
              :style="{ height: `${Math.max(8, (pageViews(point) / maxPageViews) * 100)}%` }"
              :title="`${point.day}: ${formatMetric(point.page_views)} PV / ${formatMetric(point.unique_visitors)} UV`"
            ></span>
          </div>
          <div class="trend-legend" aria-label="趋势说明">
            <span><i></i>PV</span>
          </div>
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
              <span class="rank-title">{{ source.source_name }}</span>
              <span class="rank-board">
                {{ sourceTypeLabel(source.source_type) }} · {{ formatMetric(source.unique_visitors) }} UV
              </span>
              <strong>{{ formatMetric(source.visit_count) }} PV</strong>
            </li>
          </ol>
          <p v-else class="analytics-state">当前范围内暂无访问来源。</p>
        </article>
      </section>

      <section class="top-grid" aria-label="运营榜单">
        <article>
          <div class="section-heading">
            <strong>入口页</strong>
          </div>
          <ol v-if="entryPages.length">
            <li v-for="page in entryPages" :key="page.path">
              <span :title="page.path">{{ entryPageLabel(page.title, page.path) }}</span>
              <strong>{{ formatMetric(page.visit_count) }} PV</strong>
            </li>
          </ol>
          <p v-else class="analytics-state">暂无入口页数据。</p>
        </article>
        <article>
          <div class="section-heading">
            <strong>热门主题</strong>
          </div>
          <ol v-if="overview.top_topics.length">
            <li v-for="topic in overview.top_topics" :key="topic.id">
              <span>{{ topic.title }}</span>
              <strong>{{ formatMetric(topic.view_count) }} 浏览</strong>
            </li>
          </ol>
          <p v-else class="analytics-state">暂无热门主题。</p>
        </article>
        <article>
          <div class="section-heading">
            <strong>转化信号</strong>
          </div>
          <dl class="governance-list">
            <div>
              <dt>注册</dt>
              <dd>{{ formatMetric(overview.totals.registrations) }}</dd>
            </div>
            <div>
              <dt>主题</dt>
              <dd>{{ formatMetric(overview.totals.topics) }}</dd>
            </div>
            <div>
              <dt>回复</dt>
              <dd>{{ formatMetric(overview.totals.posts) }}</dd>
            </div>
            <div>
              <dt>峰值 DAU</dt>
              <dd>{{ formatMetric(overview.totals.dau) }}</dd>
            </div>
          </dl>
        </article>
      </section>
    </template>

    <section class="data-explorer" aria-label="Data Explorer">
      <div class="section-heading data-explorer__heading">
        <div>
          <strong>数据报表</strong>
        </div>
        <UiButton
          tone="subtle"
          :disabled="!selectedReportId || exportReport.isPending.value"
          @click="exportCsv"
        >
          <template #icon><DownloadOutlined /></template>
          导出
        </UiButton>
      </div>
      <div v-if="reportsQuery.isLoading.value" class="analytics-state" role="status">正在读取预设报表…</div>
      <div v-else class="report-tabs" aria-label="预设报表">
        <button
          v-for="item in reports"
          :key="item.id"
          type="button"
          :class="{ active: item.id === selectedReportId }"
          @click="selectedReportId = item.id"
        >
          {{ item.name }}
        </button>
      </div>
      <div v-if="reportsQuery.isError.value" class="analytics-state analytics-state--error">
        预设报表读取失败。
      </div>
      <div v-else-if="reportQuery.isLoading.value" class="analytics-state" role="status">正在运行报表…</div>
      <div v-else-if="report" class="report-table-wrap">
        <table v-if="reportColumns.length" class="report-table">
          <thead>
            <tr>
              <th v-for="column in reportColumns" :key="column">{{ column }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, index) in reportRows" :key="index">
              <td v-for="column in reportColumns" :key="column">{{ reportCell(row[column]) }}</td>
            </tr>
            <tr v-if="!reportRows.length">
              <td :colspan="reportColumns.length">当前范围内没有报表行。</td>
            </tr>
          </tbody>
        </table>
        <p v-else class="analytics-state">这个预设报表没有返回列定义。</p>
      </div>
    </section>
  </UiCard>
</template>

<style scoped lang="scss" src="./AdminAnalyticsPanel.scss"></style>
