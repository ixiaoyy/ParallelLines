<script setup lang="ts">
import { currentLocale, uiText } from "@/shared/i18n/locale";
import { LineChart } from "echarts/charts";
import { GridComponent, LegendComponent, TooltipComponent } from "echarts/components";
import * as echarts from "echarts/core";
import type { ECharts, EChartsCoreOption } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";

import { sourceNameLabel, sourceTypeLabel } from "@/features/analytics/model";
import {
  formatTrafficCount,
  formatTrafficPercent,
  formatTrafficTimestamp,
  TRAFFIC_SITE_FILTERS,
  trafficActionLabel,
  trafficChange,
  trafficSiteLabel,
  trafficSiteStatus,
} from "@/features/analytics/trafficModel";
import type { TrafficSiteFilter } from "@/features/analytics/trafficModel";
import { isTrafficExcluded, setTrafficExcluded } from "@/features/analytics/trafficPrivacy";
import { useTrafficOverview } from "@/features/analytics/trafficQueries";
import UiButton from "@/shared/ui/Button.vue";

echarts.use([LineChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer]);

const props = defineProps<{ startDate: string; endDate: string; enabled: boolean }>();
const selectedSite = ref<TrafficSiteFilter>("all");
const params = computed(() => ({
  startDate: props.startDate,
  endDate: props.endDate,
  siteKey: selectedSite.value,
}));
const trafficQuery = useTrafficOverview(params, () => props.enabled);
const overview = computed(() => trafficQuery.data.value);
const totals = computed(() => overview.value?.totals);
const previous = computed(() => overview.value?.previous);
const hasData = computed(() => overview.value?.status === "ready");
const isCombined = computed(() => selectedSite.value === "all");
const retention = computed(() => overview.value?.retention);
const sites = computed(() => overview.value?.sites ?? []);
const sources = computed(() => (overview.value?.traffic_sources ?? []).slice(0, 8));
const pages = computed(() => (overview.value?.top_pages ?? []).slice(0, 10));
const actions = computed(() => (overview.value?.top_actions ?? []).slice(0, 10));
const points = computed(() => overview.value?.series ?? []);
const chartElement = ref<HTMLElement | null>(null);
const dailyTableOpen = ref(false);
const browserExcluded = ref(false);
const preferenceFeedback = ref("");
let chart: ECharts | null = null;
let resizeObserver: ResizeObserver | null = null;

const summaryMetrics = computed(() => [
  {
    key: "pv",
    label: "浏览量 PV",
    value: formatTrafficCount(totals.value?.page_views),
    change: trafficChange(totals.value?.page_views, previous.value?.page_views),
    note: "页面浏览次数，不含 API 调用",
  },
  {
    key: "uv",
    label: isCombined.value ? "跨站去重 UV" : "本站访客 UV",
    value: formatTrafficCount(isCombined.value ? totals.value?.shared_unique_visitors : totals.value?.unique_visitors),
    change: trafficChange(
      isCombined.value ? totals.value?.shared_unique_visitors : totals.value?.unique_visitors,
      isCombined.value ? previous.value?.shared_unique_visitors : previous.value?.unique_visitors,
    ),
    note: isCombined.value ? "仅共享访客标识的浏览器" : "同一站内的浏览器标识去重",
  },
  {
    key: "new",
    label: "新访客",
    value: formatTrafficCount(totals.value?.new_visitors),
    change: trafficChange(totals.value?.new_visitors, previous.value?.new_visitors),
    note: "采集以来首次识别，不含临时标识",
  },
  {
    key: "returning",
    label: "回访访客",
    value: formatTrafficCount(totals.value?.returning_visitors),
    change: trafficChange(totals.value?.returning_visitors, previous.value?.returning_visitors),
    note: "所选区间前已有访问记录",
  },
  {
    key: "retention",
    label: "7 日回访率",
    value: formatTrafficPercent(retention.value?.rate),
    change: (retention.value?.eligible_visitors ?? 0) > 0
      ? uiText("{returned} / {eligible} 位", { returned: formatTrafficCount(retention.value?.returned_visitors), eligible: formatTrafficCount(retention.value?.eligible_visitors) })
      : "尚无完整 7 日观察样本",
    note: "首次访问次日起 7 日内再次访问",
  },
  {
    key: "actions",
    label: "关键动作",
    value: formatTrafficCount(totals.value?.actions),
    change: trafficChange(totals.value?.actions, previous.value?.actions),
    note: "游戏打开、结果下载与复制点击",
  },
]);

const chartLabel = computed(() => {
  const uvLabel = uiText(isCombined.value ? "共享标识跨站去重访客" : "本站访客");
  return uiText("{site}每日浏览量与{uv}趋势，{start} 至 {end}", { site: trafficSiteLabel(selectedSite.value), uv: uvLabel, start: props.startDate, end: props.endDate });
});

const queueNotice = computed(() => {
  const queue = overview.value?.queue;
  if (queue?.status === "unavailable") return "采集队列暂不可用，当前数据可能不完整；各站业务不受统计失败阻断。";
  if (queue?.status === "full") return "采集队列已满，新事件暂不接收；流量可能少计，请检查统计后台。";
  if ((queue?.dropped_events ?? 0) > 0) return "采集曾发生丢弃，当前流量可能少计；请结合丢弃计数判断数据完整性。";
  return "";
});

/** 主页面刷新只读取缓存快照，不绕过后端缓存或触发实时汇总。 */
function refresh(): void {
  if (props.enabled) void trafficQuery.refetch();
}

defineExpose({ refresh, isFetching: trafficQuery.isFetching });

/** 切换浏览器统计排除；写入失败保留实际状态，不伪装成功。 */
function toggleBrowserExclusion(): void {
  const next = !browserExcluded.value;
  if (!setTrafficExcluded(next)) {
    preferenceFeedback.value = "浏览器未保存偏好，请检查 Cookie 权限。";
    syncBrowserExclusion();
    return;
  }
  browserExcluded.value = next;
  preferenceFeedback.value = next ? "已排除此浏览器后续访问，不删除历史记录。" : "已恢复此浏览器后续统计。";
}

/** 同步本页或其他子站已保存的浏览器偏好；不发送报表请求。 */
function syncBrowserExclusion(): void {
  browserExcluded.value = isTrafficExcluded();
}

/** 用既有 ECharts 与站点令牌展示后端日汇总；不创建采集轮询或额外网络请求。 */
function renderChart(): void {
  if (!chartElement.value || !hasData.value) {
    disposeChart();
    return;
  }
  if (!chart) {
    chart = echarts.init(chartElement.value);
    if (typeof ResizeObserver !== "undefined") {
      resizeObserver = new ResizeObserver(() => chart?.resize());
      resizeObserver.observe(chartElement.value);
    }
  }
  const style = getComputedStyle(chartElement.value);
  const primary = style.getPropertyValue("--primary").trim() || "#409eff";
  const secondary = style.getPropertyValue("--accent-geek").trim() || "#10b981";
  const muted = style.getPropertyValue("--analytics-muted").trim() || "#64748b";
  const border = style.getPropertyValue("--border").trim() || "#e2e8f0";
  const uvName = uiText(isCombined.value ? "跨站去重 UV" : "本站 UV");
  const option: EChartsCoreOption = {
    animation: !window.matchMedia("(prefers-reduced-motion: reduce)").matches,
    animationDuration: 180,
    color: [primary, secondary],
    grid: { left: 8, right: 14, top: 18, bottom: 42, containLabel: true },
    legend: {
      bottom: 0,
      left: 0,
      icon: "roundRect",
      itemWidth: 12,
      itemHeight: 6,
      textStyle: { color: muted, fontSize: 12 },
    },
    tooltip: { trigger: "axis", confine: true },
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: points.value.map((point) => point.day.slice(5).replace("-", "/")),
      axisLabel: { color: muted, hideOverlap: true, fontSize: 11 },
      axisLine: { lineStyle: { color: border } },
      axisTick: { show: false },
    },
    yAxis: {
      type: "value",
      min: 0,
      minInterval: 1,
      axisLabel: { color: muted },
      splitLine: { lineStyle: { color: border, opacity: 0.7 } },
    },
    series: [
      { name: uiText("浏览量 PV"), type: "line", data: points.value.map((point) => point.page_views), showSymbol: points.value.length <= 14, smooth: false, lineStyle: { width: 2.5 } },
      { name: uvName, type: "line", data: points.value.map((point) => isCombined.value ? point.shared_unique_visitors : point.unique_visitors), showSymbol: points.value.length <= 14, smooth: false, lineStyle: { width: 2 } },
    ],
  };
  chart.setOption(option, { notMerge: true });
}

/** 释放图表、尺寸观察器，避免切换状态或离页后继续占用资源。 */
function disposeChart(): void {
  resizeObserver?.disconnect();
  resizeObserver = null;
  chart?.dispose();
  chart = null;
}

watch([overview, chartElement, currentLocale], async () => {
  await nextTick();
  renderChart();
}, { flush: "post" });

onMounted(() => {
  syncBrowserExclusion();
  window.addEventListener("pl:traffic-preference", syncBrowserExclusion);
  window.addEventListener("focus", syncBrowserExclusion);
});

onBeforeUnmount(() => {
  disposeChart();
  window.removeEventListener("pl:traffic-preference", syncBrowserExclusion);
  window.removeEventListener("focus", syncBrowserExclusion);
});
</script>

<template>
  <section class="traffic-panel" aria-labelledby="traffic-title">
    <header class="traffic-heading">
      <div>
        <span class="traffic-eyebrow">{{ uiText('流量与吸引力') }}</span>
        <h2 id="traffic-title">{{ uiText('跨站流量') }}</h2>
        <p>{{ uiText('看访客从哪里来、喜欢什么，以及是否再次回来。') }}</p>
      </div>
      <span class="traffic-delay-label">{{ uiText('异步采集 · 非实时') }}</span>
    </header>

    <nav class="traffic-site-filters" :aria-label="uiText('选择分析站点')">
      <button
        v-for="site in TRAFFIC_SITE_FILTERS"
        :key="site.key"
        type="button"
        :class="{ active: selectedSite === site.key }"
        :aria-pressed="selectedSite === site.key"
        @click="selectedSite = site.key"
      >{{ uiText(site.label) }}</button>
    </nav>

    <div v-if="trafficQuery.isLoading.value" class="traffic-state" role="status">
      {{ uiText('正在读取流量汇总…') }}
    </div>
    <div v-else-if="trafficQuery.isError.value && !overview" class="traffic-state traffic-state--error" role="alert">
      <div><strong>{{ uiText('流量汇总暂时不可用') }}</strong><p>{{ uiText('统计失败不影响各站业务，原主站报表仍可独立查看。') }}</p></div>
      <UiButton tone="subtle" @click="refresh">{{ uiText('重新加载') }}</UiButton>
    </div>

    <template v-if="overview">
      <div class="traffic-freshness">
        <span>{{ uiText('数据截止') }} <strong>{{ formatTrafficTimestamp(overview.data_through) }}</strong></span>
        <span>{{ uiText('汇总生成') }} {{ formatTrafficTimestamp(overview.generated_at) }}</span>
        <span>{{ uiText("上海时间 · 缓存 {minutes} 分钟", { minutes: Math.round((overview.cache_seconds ?? 300) / 60) }) }}</span>
      </div>
      <div v-if="trafficQuery.isError.value" class="traffic-state traffic-state--warning" role="alert">
        {{ uiText('更新失败，当前保留上次成功读取的汇总。请稍后主动刷新。') }}
      </div>
      <div v-if="queueNotice" class="traffic-state traffic-state--warning" role="status">
        <div>
          <strong>{{ uiText(queueNotice) }}</strong>
          <p>{{ uiText("待处理 {pending} 条 · 丢弃 {dropped} 条", { pending: formatTrafficCount(overview.queue?.pending), dropped: formatTrafficCount(overview.queue?.dropped_events) }) }}</p>
        </div>
      </div>

      <div v-if="overview.status === 'disabled'" class="traffic-state" role="status">
        <div><strong>{{ uiText('跨站流量采集尚未启用') }}</strong><p>{{ uiText('启用采集与后台处理后，从接入日开始统计；历史主站报表保持原口径。') }}</p></div>
      </div>
      <div v-else-if="overview.status === 'not_connected'" class="traffic-state" role="status">
        <div><strong>{{ uiText("尚未收到{site}的流量数据", { site: isCombined ? uiText("各站") : trafficSiteLabel(selectedSite) }) }}</strong><p>{{ uiText('未接入不代表没有访客。请先检查站点采集、队列与后台处理状态。') }}</p></div>
      </div>

      <template v-if="hasData">
        <section class="traffic-metrics" :aria-label="uiText('核心流量指标')">
          <article v-for="metric in summaryMetrics" :key="metric.key" class="traffic-metric">
            <h3>{{ uiText(metric.label) }}</h3>
            <strong>{{ metric.value }}</strong>
            <span class="traffic-metric-change">{{ metric.change }}</span>
            <small>{{ uiText(metric.note) }}</small>
          </article>
        </section>

        <div class="traffic-identity-note">
          <strong>{{ uiText('UV 按浏览器标识统计，不等于真人数。') }}</strong>
          <span>{{ uiText("共享标识 {shared} · 仅站内标识 {siteOnly} · 临时标识 {ephemeral}。站内与临时标识不能直接合并成全站人数。", { shared: formatTrafficCount(totals?.shared_unique_visitors), siteOnly: formatTrafficCount(totals?.site_only_visitors), ephemeral: formatTrafficCount(totals?.ephemeral_visitors) }) }}</span>
        </div>

        <section class="traffic-trend" aria-labelledby="traffic-trend-title">
          <div class="traffic-subheading">
            <div><h3 id="traffic-trend-title">{{ uiText("{site}访问趋势", { site: trafficSiteLabel(selectedSite) }) }}</h3><p>{{ uiText('与前一个等长区间比较；同一浏览器跨日只在区间 UV 中计一次。') }}</p></div>
            <button class="traffic-text-button" type="button" :aria-expanded="dailyTableOpen" aria-controls="traffic-daily-table" @click="dailyTableOpen = !dailyTableOpen">{{ dailyTableOpen ? uiText('收起日数据') : uiText('查看日数据') }}</button>
          </div>
          <div ref="chartElement" class="traffic-chart" role="img" :aria-label="chartLabel"></div>
          <div v-if="dailyTableOpen" id="traffic-daily-table" class="traffic-table-wrap traffic-daily-table">
            <table><thead><tr><th scope="col">{{ uiText('日期') }}</th><th scope="col">{{ uiText('浏览量 PV') }}</th><th scope="col">{{ isCombined ? uiText('跨站去重 UV') : uiText('本站 UV') }}</th></tr></thead><tbody><tr v-for="point in points" :key="point.day"><td>{{ point.day }}</td><td>{{ formatTrafficCount(point.page_views) }}</td><td>{{ formatTrafficCount(isCombined ? point.shared_unique_visitors : point.unique_visitors) }}</td></tr></tbody></table>
          </div>
          <p v-if="retention?.cohort_start && retention?.cohort_end" class="traffic-footnote">{{ uiText("7 日回访观察：{start} 至 {end} 首次出现的访客，仅纳入已有完整 7 日观察期的样本。", { start: retention.cohort_start, end: retention.cohort_end }) }}</p>
        </section>
      </template>

      <section class="traffic-sites" aria-labelledby="traffic-sites-title">
        <div class="traffic-subheading"><div><h3 id="traffic-sites-title">{{ uiText('各站流量与接入状态') }}</h3><p>{{ uiText('各站 UV 各自去重，不能相加作为全站 UV；模型网关仅计网页访问。') }}</p></div></div>
        <div class="traffic-table-wrap" tabindex="0" role="region" :aria-label="uiText('各站流量明细，可横向滚动')">
          <table class="traffic-sites-table">
            <thead><tr><th scope="col">{{ uiText('站点') }}</th><th scope="col">{{ uiText('状态') }}</th><th scope="col">{{ uiText('浏览量 PV') }}</th><th scope="col">{{ uiText('本站 UV') }}</th><th scope="col">{{ uiText('关键动作') }}</th><th scope="col">{{ uiText('最后上报') }}</th></tr></thead>
            <tbody><tr v-for="site in sites" :key="site.site_key" :class="{ 'is-selected': selectedSite === site.site_key }"><th scope="row"><button type="button" class="traffic-text-button" :aria-pressed="selectedSite === site.site_key" @click="selectedSite = site.site_key">{{ site.name }}</button></th><td><span class="traffic-status" :class="`traffic-status--${site.status}`">{{ trafficSiteStatus(site.status) }}</span></td><td>{{ formatTrafficCount(site.page_views) }}</td><td>{{ formatTrafficCount(site.unique_visitors) }}</td><td>{{ formatTrafficCount(site.actions) }}</td><td>{{ formatTrafficTimestamp(site.last_received_at) }}</td></tr></tbody>
          </table>
        </div>
        <p class="traffic-footnote">{{ uiText('窄屏可横向滑动查看完整列。未接入显示 —，已接入但区间没有访问才显示 0；近期无上报不代表站点故障。') }}</p>
      </section>

      <template v-if="hasData">
        <section class="traffic-rankings" :aria-label="uiText('流量来源与热门内容')">
          <article>
            <div class="traffic-subheading"><div><h3>{{ uiText('流量来源') }}</h3><p>{{ uiText('当前站点范围 · 最多显示前 8 项') }}</p></div></div>
            <div class="traffic-table-wrap"><table><thead><tr><th scope="col">{{ uiText('来源') }}</th><th scope="col">PV</th><th scope="col">UV</th></tr></thead><tbody><tr v-for="source in sources" :key="`${source.source_type}:${source.source_name}`"><td><span>{{ sourceNameLabel(source.source_name) }}</span><small>{{ sourceTypeLabel(source.source_type) }}</small></td><td>{{ formatTrafficCount(source.page_views) }}</td><td>{{ formatTrafficCount(source.unique_visitors) }}</td></tr><tr v-if="!sources.length"><td colspan="3" class="traffic-empty">{{ uiText('当前范围内没有来源记录。') }}</td></tr></tbody></table></div>
          </article>
          <article>
            <div class="traffic-subheading"><div><h3>{{ uiText('热门页面') }}</h3><p>{{ uiText('按浏览量排序 · 最多显示前 10 项') }}</p></div></div>
            <div class="traffic-table-wrap"><table><thead><tr><th scope="col">{{ uiText('页面') }}</th><th scope="col">PV</th><th scope="col">UV</th></tr></thead><tbody><tr v-for="page in pages" :key="`${page.site_key}:${page.path}`"><td><code>{{ page.path }}</code><small>{{ trafficSiteLabel(page.site_key) }}</small></td><td>{{ formatTrafficCount(page.page_views) }}</td><td>{{ formatTrafficCount(page.unique_visitors) }}</td></tr><tr v-if="!pages.length"><td colspan="3" class="traffic-empty">{{ uiText('当前范围内没有页面记录。') }}</td></tr></tbody></table></div>
          </article>
        </section>
        <section class="traffic-actions" aria-labelledby="traffic-actions-title">
          <div class="traffic-subheading"><div><h3 id="traffic-actions-title">{{ uiText('从浏览到使用') }}</h3><p>{{ uiText('已接入的关键动作，按触发次数排序；打开或发起不代表成功完成。') }}</p></div></div>
          <div class="traffic-table-wrap"><table><thead><tr><th scope="col">{{ uiText('动作与页面') }}</th><th scope="col">{{ uiText('触发次数') }}</th><th scope="col">{{ uiText('访客标识数') }}</th></tr></thead><tbody><tr v-for="action in actions" :key="`${action.site_key}:${action.event_name}:${action.path}`"><td><span>{{ trafficSiteLabel(action.site_key) }} · {{ trafficActionLabel(action.event_name) }}</span><code>{{ action.path }}</code></td><td>{{ formatTrafficCount(action.count) }}</td><td>{{ formatTrafficCount(action.unique_visitors) }}</td></tr><tr v-if="!actions.length"><td colspan="3" class="traffic-empty">{{ uiText('当前范围内没有关键动作记录，不能据此判断无人使用。') }}</td></tr></tbody></table></div>
        </section>
      </template>
    </template>

    <footer class="traffic-privacy">
      <div><strong>{{ uiText('排除自己的访问') }}</strong><p>{{ uiText('仅影响当前浏览器及本站各子站的后续采集，不删除历史记录、不更改账号。') }}</p><span v-if="preferenceFeedback" aria-live="polite">{{ uiText(preferenceFeedback) }}</span></div>
      <button type="button" class="traffic-preference-button" :aria-pressed="browserExcluded" @click="toggleBrowserExclusion">{{ browserExcluded ? uiText('已排除此浏览器 · 恢复统计') : uiText('排除此浏览器统计') }}</button>
    </footer>
  </section>
</template>

<style scoped lang="scss" src="./AdminTrafficPanel.scss"></style>
