<script setup lang="ts">
import { computed, ref, watch } from "vue";

import { formatMetric, reportCell } from "@/features/analytics/model";
import type { DataExplorerReportSummary } from "@/features/analytics/model";
import {
  useAnalyticsOverview,
  useDataExplorerReport,
  useDataExplorerReports,
  useExportDataExplorerReport,
} from "@/features/analytics/queries";
import UiCard from "@/shared/ui/Card.vue";

const today = new Date();
const prior = new Date(today);
prior.setDate(today.getDate() - 29);
const startDate = ref(toDateInput(prior));
const endDate = ref(toDateInput(today));
const selectedReportId = ref("");
const range = computed(() => ({ startDate: startDate.value, endDate: endDate.value }));

const overviewQuery = useAnalyticsOverview(range);
const overview = computed(() => overviewQuery.data.value);
const reportsQuery = useDataExplorerReports();
const reports = computed(() => reportsQuery.data.value ?? []);
const reportQuery = useDataExplorerReport(selectedReportId, range, computed(() => Boolean(selectedReportId.value)));
const report = computed(() => reportQuery.data.value);
const exportReport = useExportDataExplorerReport();
const maxTopics = computed(() =>
  Math.max(1, ...(overview.value?.series ?? []).map((point) => point.topics ?? 0)),
);
const selectedReport = computed<DataExplorerReportSummary | null>(
  () => reports.value.find((item) => item.id === selectedReportId.value) ?? null,
);

watch(
  reports,
  (items) => {
    if (!selectedReportId.value && items[0]) {
      selectedReportId.value = items[0].id;
    }
  },
  { immediate: true },
);

function toDateInput(date: Date): string {
  return date.toISOString().slice(0, 10);
}

function exportCsv() {
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
    <div class="analytics-title">
      <div>
        <span>Analytics</span>
        <h2>运营分析与 Data Explorer</h2>
      </div>
      <p>统计核心增长、内容和治理指标，并运行安全的预设查询。</p>
    </div>

    <div class="analytics-toolbar">
      <label>
        起始日期
        <input v-model="startDate" type="date" />
      </label>
      <label>
        结束日期
        <input v-model="endDate" type="date" />
      </label>
      <span class="toolbar-note">报表按日期范围过滤，CSV 导出会写入审计日志。</span>
    </div>

    <div v-if="overviewQuery.isLoading.value" class="analytics-state">正在计算运营指标…</div>
    <div v-else-if="overviewQuery.isError.value" class="analytics-state analytics-state--error">
      报表暂时不可用，请确认当前账号具备管理员权限。
    </div>
    <template v-else-if="overview">
      <section class="metric-grid" aria-label="核心指标">
        <article v-for="(value, key) in overview.totals" :key="key">
          <span>{{ key }}</span>
          <strong>{{ formatMetric(value) }}</strong>
        </article>
      </section>

      <section class="trend-card" aria-label="主题趋势">
        <div class="section-heading">
          <strong>主题趋势</strong>
          <span>{{ overview.start_date }} → {{ overview.end_date }}</span>
        </div>
        <div class="trend-bars">
          <span
            v-for="point in overview.series"
            :key="point.day"
            :style="{ height: `${Math.max(8, ((point.topics ?? 0) / maxTopics) * 100)}%` }"
            :title="`${point.day}: ${point.topics ?? 0} 个主题`"
          ></span>
        </div>
      </section>

      <section class="top-grid">
        <article>
          <div class="section-heading"><strong>Top 版块</strong></div>
          <ol>
            <li v-for="board in overview.top_boards" :key="board.id">
              <span>{{ board.name }}</span>
              <strong>{{ formatMetric(board.topic_count) }} 主题</strong>
            </li>
          </ol>
        </article>
        <article>
          <div class="section-heading"><strong>Top 主题</strong></div>
          <ol>
            <li v-for="topic in overview.top_topics" :key="topic.id">
              <span>{{ topic.title }}</span>
              <strong>{{ formatMetric(topic.reply_count) }} 回复</strong>
            </li>
          </ol>
        </article>
        <article>
          <div class="section-heading"><strong>活跃成员</strong></div>
          <ol>
            <li v-for="user in overview.top_users" :key="user.id">
              <span>{{ user.username }}</span>
              <strong>{{ formatMetric(user.post_count) }} 帖</strong>
            </li>
          </ol>
        </article>
      </section>
    </template>

    <section class="data-explorer" aria-label="Data Explorer">
      <div class="section-heading">
        <div>
          <strong>Data Explorer</strong>
          <span>{{ selectedReport?.description ?? "选择一个预设报表运行" }}</span>
        </div>
        <button
          class="export-button"
          type="button"
          :disabled="!selectedReportId || exportReport.isPending.value"
          @click="exportCsv"
        >
          导出 CSV
        </button>
      </div>
      <div class="report-tabs">
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
      <div v-else-if="reportQuery.isLoading.value" class="analytics-state">正在运行报表…</div>
      <div v-else-if="report" class="report-table-wrap">
        <table class="report-table">
          <thead>
            <tr>
              <th v-for="column in report.columns" :key="column">{{ column }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, index) in report.rows" :key="index">
              <td v-for="column in report.columns" :key="column">{{ reportCell(row[column]) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </UiCard>
</template>

<style scoped lang="scss" src="./AdminAnalyticsPanel.scss"></style>
