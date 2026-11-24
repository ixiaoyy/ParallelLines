import type { components } from "@/shared/api/generated";
import { computed } from "vue";
import { currentLocale, uiText } from "@/shared/i18n/locale";

export type TrafficOverview = components["schemas"]["TrafficOverviewResponse"];
export type TrafficSiteFilter = TrafficOverview["site_key"];
export type TrafficSite = components["schemas"]["TrafficSite"];
export type TrafficPoint = components["schemas"]["TrafficPoint"];

export const TRAFFIC_SITE_FILTERS: ReadonlyArray<{ key: TrafficSiteFilter; label: string }> = [
  { key: "all", label: "综合" },
  { key: "games", label: "游戏" },
  { key: "forum", label: "圈子" },
  { key: "tools", label: "工具" },
  { key: "chat", label: "Chat" },
  { key: "api", label: "模型网关" },
];

// 仅格式化展示；不改变空值、百分比口径或后端计数。
const countFormatter = computed(() => new Intl.NumberFormat(currentLocale.value));
const percentageFormatter = computed(() => new Intl.NumberFormat(currentLocale.value, { maximumFractionDigits: 1 }));

/** 显示流量计数；未接入或数据缺失保留破折号，不转换为零。 */
export function formatTrafficCount(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : countFormatter.value.format(value);
}

/** 比较相同长度的两个区间；前期为零时不生成无穷大的增长率。 */
export function trafficChange(
  current: number | null | undefined,
  previous: number | null | undefined,
): string {
  if (current === null || current === undefined || previous === null || previous === undefined) {
    return uiText("暂无可比数据");
  }
  if (current === previous) return uiText("与前期持平");
  if (previous === 0) return uiText("前期为 0，本期有新增");
  const percent = ((current - previous) / previous) * 100;
  return uiText("较前期 {change}%", { change: `${percent > 0 ? "+" : ""}${percentageFormatter.value.format(percent)}` });
}

/** 显示后端已经计算的百分比，空值保留未形成状态。 */
export function formatTrafficPercent(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : `${percentageFormatter.value.format(value)}%`;
}

/** 将固定站点标识转为产品名称，不将网页访问和模型调用混为同一指标。 */
export function trafficSiteLabel(siteKey: TrafficSiteFilter): string {
  const site = TRAFFIC_SITE_FILTERS.find((item) => item.key === siteKey);
  return site ? uiText(site.label) : siteKey;
}

/** 展示采集状态；长时间没有事件仅提示待确认，不推断站点服务故障。 */
export function trafficSiteStatus(status: TrafficSite["status"]): string {
  const labels: Record<TrafficSite["status"], string> = {
    disabled: "未启用",
    not_connected: "未接入",
    no_activity: "区间无访问",
    collecting: "有采集记录",
    stale: "近期无上报",
  };
  return Object.hasOwn(labels, status) ? uiText(labels[status]) : status;
}

/** 展示埋点含义；动作表示点击，不代表真实游玩、转换或下载成功。 */
export function trafficActionLabel(eventName: string): string {
  const labels: Record<string, string> = {
    page_view: "页面浏览",
    game_open: "游戏打开",
    tool_download: "结果下载点击",
    tool_copy: "结果复制点击",
  };
  return Object.hasOwn(labels, eventName) ? uiText(labels[eventName]) : eventName;
}

/** 按统一的上海时区展示采集和汇总时刻；空值或无效值不冒充当前时间。 */
export function formatTrafficTimestamp(value: string | null | undefined): string {
  if (!value) return uiText("尚无记录");
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return uiText("尚无记录");
  return new Intl.DateTimeFormat(currentLocale.value, {
    timeZone: "Asia/Shanghai",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}
