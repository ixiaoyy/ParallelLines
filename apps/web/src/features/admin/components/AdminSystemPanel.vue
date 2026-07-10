<script setup lang="ts">
import {
  CheckCircleFilled,
  ClockCircleOutlined,
  CloudServerOutlined,
  DatabaseOutlined,
  ExclamationCircleFilled,
  FieldTimeOutlined,
  MailOutlined,
  ReloadOutlined,
  SendOutlined,
  SyncOutlined,
} from "@ant-design/icons-vue";
import { computed } from "vue";
import type { Component } from "vue";

import type { AdminSystemOverviewResponse } from "@/features/admin/model";
import { useAdminSystem } from "@/features/admin/queries";
import { relativeTime } from "@/shared/lib/format";
import UiButton from "@/shared/ui/Button.vue";

interface RecentErrorSummary {
  key: string;
  taskLabel: string;
  count: number;
  lastOccurredAt: string;
  message: string;
  action: string;
}

const systemQuery = useAdminSystem();
const system = computed(() => systemQuery.data.value);
const statItems = computed(() => {
  const stats: AdminSystemOverviewResponse["stats"] | undefined = system.value?.stats;
  if (!stats) {
    return [];
  }
  return [
    { label: "用户", value: stats.users },
    { label: "版块", value: stats.boards },
    { label: "主题", value: stats.topics },
    { label: "回复", value: stats.posts },
    { label: "待处理举报", value: stats.pending_flags },
    { label: "审计记录", value: stats.audit_logs },
  ];
});
const recentErrorSummaries = computed(() => summarizeRecentErrors(system.value?.recent_errors ?? []));
const degradedServices = computed(() => system.value?.services.filter((service) => service.status !== "ok") ?? []);
const issueCount = computed(
  () => degradedServices.value.length + ((system.value?.queue.dead ?? 0) > 0 ? 1 : 0),
);
const lastUpdatedLabel = computed(() => {
  const updatedAt = systemQuery.dataUpdatedAt.value;
  if (!updatedAt) {
    return "尚未更新";
  }
  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date(updatedAt));
});

// Reloads the system overview while preserving the previous successful payload during the request.
// Key parameters: none. Return value: none. Side effect: refetches `/admin/system`.
function refreshSystem(): void {
  void systemQuery.refetch();
}

// Maps backend service identifiers to labels used in the operations console.
// Key parameter `name` is the API service id. Return value is a Chinese display label; side effect: none.
function serviceNameLabel(name: string): string {
  const labels: Record<string, string> = {
    cache: "缓存服务",
    database: "主数据库",
    mail: "邮件服务",
    workers: "后台任务",
  };
  return labels[name] ?? name;
}

// Maps backend service identifiers to a consistent Ant Design icon component.
// Key parameter `name` is the API service id. Return value is a renderable icon component; side effect: none.
function serviceIcon(name: string): Component {
  const icons: Record<string, Component> = {
    cache: CloudServerOutlined,
    database: DatabaseOutlined,
    mail: MailOutlined,
    workers: SyncOutlined,
  };
  return icons[name] ?? CloudServerOutlined;
}

// Maps backend service status values to short dashboard labels.
// Key parameter `status` is the API status value. Return value is display text; side effect: none.
function serviceStatusLabel(status: string): string {
  if (status === "ok") {
    return "运行正常";
  }
  if (status === "degraded") {
    return "需要留意";
  }
  return "状态未知";
}

// Returns a semantic class suffix for service state styling.
// Key parameter `status` is the API status value. Return value is a stable class suffix; side effect: none.
function serviceStatusClass(status: string): string {
  if (status === "ok") {
    return "success";
  }
  if (status === "degraded") {
    return "warning";
  }
  return "neutral";
}

// Formats worker cadence seconds as a compact operator-facing duration.
// Key parameter `seconds` is a non-negative interval. Return value is Chinese duration text; side effect: none.
function intervalLabel(seconds: number | undefined): string {
  if (!seconds || seconds < 60) {
    return `${seconds ?? 0} 秒`;
  }
  if (seconds % 3600 === 0) {
    return `${seconds / 3600} 小时`;
  }
  return `${Math.round(seconds / 60)} 分钟`;
}

// Converts audit target identifiers into concise labels without inventing entity metadata.
// Key parameters are API target type/id fields. Return value is display text; side effect: none.
function auditTargetLabel(targetType: string, targetId: string): string {
  const labels: Record<string, string> = {
    user: "用户",
    topic: "主题",
    post: "回复",
    flag: "举报",
    board: "版块",
  };
  const label = labels[targetType] ?? targetType;
  return targetId ? `${label} · ${targetId.slice(0, 8)}` : label;
}

// Collapses raw dead-letter rows into operator-friendly task summaries.
// Key parameter `errors` is the `/admin/system` recent_errors payload. Return value is grouped summaries sorted by recency; side effect: none.
function summarizeRecentErrors(errors: Record<string, unknown>[]): RecentErrorSummary[] {
  const groups = new Map<string, RecentErrorSummary>();
  for (const error of errors) {
    const taskName = stringValue(error.task_name, "unknown_task");
    const rawError = stringValue(error.error);
    const occurredAt = stringValue(error.occurred_at);
    const category = errorCategory(rawError);
    const key = `${taskName}:${category}`;
    const existing = groups.get(key);

    if (existing) {
      existing.count += 1;
      if (isLater(occurredAt, existing.lastOccurredAt)) {
        existing.lastOccurredAt = occurredAt;
      }
      continue;
    }

    groups.set(key, {
      key,
      taskLabel: taskNameLabel(taskName),
      count: 1,
      lastOccurredAt: occurredAt,
      message: errorMessage(category),
      action: errorAction(category),
    });
  }

  return Array.from(groups.values()).sort(
    (left, right) => Date.parse(right.lastOccurredAt) - Date.parse(left.lastOccurredAt),
  );
}

// Reads an unknown API field as a string while keeping template rendering predictable.
// Key parameter `value` is an untyped API field; `fallback` is returned for absent values. Return value is a string; side effect: none.
function stringValue(value: unknown, fallback = ""): string {
  return typeof value === "string" && value.trim() ? value : fallback;
}

// Maps background task identifiers to labels suitable for the admin dashboard.
// Key parameter `taskName` is a worker task id. Return value is Chinese display text; side effect: none.
function taskNameLabel(taskName: string): string {
  const labels: Record<string, string> = {
    collect_frontier_news: "资讯采集任务",
    send_digest_emails: "邮件摘要任务",
    send_notification_email: "通知邮件任务",
    create_notification: "站内通知任务",
    deliver_webhook: "Webhook 投递任务",
    recompute_hot_scores: "热度计算任务",
    cleanup_expired_uploads: "临时上传清理",
    cleanup_expired_sessions: "登录会话清理",
  };
  return labels[taskName] ?? "后台任务";
}

// Classifies raw worker errors into stable UI copy buckets.
// Key parameter `rawError` is the backend last_error text. Return value names a known category; side effect: none.
function errorCategory(rawError: string): string {
  if (rawError.includes("offset-naive") && rawError.includes("offset-aware")) {
    return "timezone";
  }
  return "unknown";
}

// Converts a worker error category into a concise Chinese summary.
// Key parameter `category` is produced by errorCategory. Return value is operator-facing text; side effect: none.
function errorMessage(category: string): string {
  if (category === "timezone") {
    return "历史失败：任务时间格式不一致，本次更新已兼容。";
  }
  return "后台任务执行失败。";
}

// Converts a worker error category into a next-step hint for administrators.
// Key parameter `category` is produced by errorCategory. Return value is Chinese guidance; side effect: none.
function errorAction(category: string): string {
  if (category === "timezone") {
    return "等待下一轮定时任务自动运行；旧失败记录会保留在任务日志中。";
  }
  return "如持续出现，请查看服务端任务日志定位具体原因。";
}

// Compares two optional ISO-like timestamp strings for summary ordering.
// Key parameters are API timestamps. Return value is true when `candidate` is later than `current`; side effect: none.
function isLater(candidate: string, current: string): boolean {
  const candidateTime = Date.parse(candidate);
  const currentTime = Date.parse(current);
  if (Number.isNaN(candidateTime)) {
    return false;
  }
  if (Number.isNaN(currentTime)) {
    return true;
  }
  return candidateTime > currentTime;
}
</script>

<template>
  <section class="system-panel" aria-labelledby="admin-system-title">
    <header class="system-panel__header">
      <div>
        <span class="system-panel__context">基础设施</span>
        <h1 id="admin-system-title">系统运行</h1>
        <p>查看核心服务、后台任务、邮件与审计记录。</p>
      </div>
      <button
        type="button"
        class="system-refresh-button"
        :disabled="systemQuery.isFetching.value"
        @click="refreshSystem"
      >
        <ReloadOutlined :class="{ 'is-spinning': systemQuery.isFetching.value }" aria-hidden="true" />
        {{ systemQuery.isFetching.value ? "刷新中…" : "刷新状态" }}
      </button>
    </header>

    <div v-if="systemQuery.isLoading.value" class="system-loading" role="status">
      <span class="sr-only">系统状态加载中…</span>
      <i v-for="index in 9" :key="index" />
    </div>

    <section v-else-if="systemQuery.isError.value" class="system-error" role="alert">
      <ExclamationCircleFilled aria-hidden="true" />
      <div>
        <strong>系统状态暂时无法读取</strong>
        <p>请检查网络或管理员权限后重新加载。</p>
      </div>
      <UiButton tone="subtle" :disabled="systemQuery.isFetching.value" @click="refreshSystem">
        {{ systemQuery.isFetching.value ? "重试中…" : "重新加载" }}
      </UiButton>
    </section>

    <template v-else-if="system">
      <div class="system-overall-status" :class="{ 'has-issues': issueCount > 0 }" role="status">
        <span class="system-overall-status__signal">
          <ExclamationCircleFilled v-if="issueCount > 0" aria-hidden="true" />
          <CheckCircleFilled v-else aria-hidden="true" />
        </span>
        <div>
          <strong>{{ issueCount > 0 ? `${issueCount} 项运行状态需要留意` : "核心服务运行正常" }}</strong>
          <p>
            {{ issueCount > 0 ? "请检查服务状态和失败任务摘要。" : "服务与任务队列均未返回异常状态。" }}
          </p>
        </div>
        <time><ClockCircleOutlined aria-hidden="true" />{{ lastUpdatedLabel }} 更新</time>
      </div>

      <section class="system-stat-strip" aria-label="站点数据概览">
        <div v-for="stat in statItems" :key="stat.label">
          <span>{{ stat.label }}</span>
          <strong>{{ stat.value }}</strong>
        </div>
      </section>

      <section class="system-section" aria-labelledby="system-services-title">
        <header class="system-section__header">
          <div>
            <span>实时检测</span>
            <h2 id="system-services-title">服务状态</h2>
          </div>
          <strong>{{ system.services.length - degradedServices.length }} 正常 · {{ degradedServices.length }} 提醒</strong>
        </header>
        <div v-if="system.services.length" class="system-service-list">
          <div v-for="service in system.services" :key="service.name" class="system-service-row">
            <span :class="`system-service-row__icon is-${serviceStatusClass(service.status)}`">
              <component :is="serviceIcon(service.name)" aria-hidden="true" />
            </span>
            <div>
              <strong>{{ serviceNameLabel(service.name) }}</strong>
              <small>{{ service.detail || "服务未返回更多说明" }}</small>
            </div>
            <span :class="`system-status-pill is-${serviceStatusClass(service.status)}`">
              <CheckCircleFilled v-if="service.status === 'ok'" aria-hidden="true" />
              <ExclamationCircleFilled v-else aria-hidden="true" />
              {{ serviceStatusLabel(service.status) }}
            </span>
          </div>
        </div>
        <div v-else class="system-empty">系统接口没有返回服务检测项。</div>
      </section>

      <section class="system-section" aria-labelledby="system-queue-title">
        <header class="system-section__header">
          <div>
            <span>异步任务</span>
            <h2 id="system-queue-title">任务队列</h2>
          </div>
          <div class="system-queue-counts">
            <span>等待 <strong>{{ system.queue.queued ?? 0 }}</strong></span>
            <span>执行中 <strong>{{ system.queue.running ?? 0 }}</strong></span>
            <span>失败 <strong :class="{ 'is-danger': (system.queue.dead ?? 0) > 0 }">{{ system.queue.dead ?? 0 }}</strong></span>
          </div>
        </header>

        <div class="system-queue-overview">
          <dl>
            <div>
              <dt>工作进程</dt>
              <dd><code>{{ system.queue.worker || "未报告" }}</code></dd>
            </div>
            <div>
              <dt>轮询间隔</dt>
              <dd>{{ intervalLabel(system.queue.poll_seconds) }}</dd>
            </div>
            <div>
              <dt>单批数量</dt>
              <dd>{{ system.queue.batch_size }}</dd>
            </div>
            <div>
              <dt>失败重试</dt>
              <dd>{{ intervalLabel(system.queue.retry_delay_seconds) }}</dd>
            </div>
          </dl>

          <div class="system-error-summary">
            <header>
              <FieldTimeOutlined aria-hidden="true" />
              <strong>失败记录摘要</strong>
              <span>{{ recentErrorSummaries.length }} 类</span>
            </header>
            <ol v-if="recentErrorSummaries.length">
              <li v-for="error in recentErrorSummaries" :key="error.key">
                <span>
                  <strong>{{ error.taskLabel }}</strong>
                  <small>{{ error.message }}</small>
                  <small>{{ error.action }}</small>
                </span>
                <span>
                  <em>{{ error.count }} 次</em>
                  <time v-if="error.lastOccurredAt">{{ relativeTime(error.lastOccurredAt) }}</time>
                </span>
              </li>
            </ol>
            <div v-else class="system-empty is-compact">没有近期失败记录。</div>
          </div>
        </div>
      </section>

      <div class="system-log-grid">
        <section class="system-section" aria-labelledby="system-mail-title">
          <header class="system-section__header">
            <div>
              <span>最近发送</span>
              <h2 id="system-mail-title">邮件日志</h2>
            </div>
            <strong>{{ system.recent_email_logs.length }} 条</strong>
          </header>
          <ol v-if="system.recent_email_logs.length" class="system-log-list">
            <li v-for="email in system.recent_email_logs" :key="`${email.kind}-${email.to_email}-${email.sent_at}`">
              <SendOutlined aria-hidden="true" />
              <span>
                <strong>{{ email.subject }}</strong>
                <small>{{ email.to_email }} · {{ email.kind }}</small>
              </span>
              <time>{{ relativeTime(email.sent_at) }}</time>
            </li>
          </ol>
          <div v-else class="system-empty">暂无邮件发送记录。</div>
        </section>

        <section class="system-section" aria-labelledby="system-audit-title">
          <header class="system-section__header">
            <div>
              <span>管理员操作</span>
              <h2 id="system-audit-title">最近审计</h2>
            </div>
            <strong>{{ system.recent_audit_logs.length }} 条</strong>
          </header>
          <ol v-if="system.recent_audit_logs.length" class="system-log-list">
            <li v-for="log in system.recent_audit_logs" :key="log.id">
              <CheckCircleFilled aria-hidden="true" />
              <span>
                <strong>{{ log.action }}</strong>
                <small>{{ log.actor_name || "系统" }} · {{ auditTargetLabel(log.target_type, log.target_id) }}</small>
              </span>
              <time>{{ relativeTime(log.created_at) }}</time>
            </li>
          </ol>
          <div v-else class="system-empty">暂无审计记录。</div>
        </section>
      </div>
    </template>

    <div v-else class="system-empty">系统接口没有返回可展示的数据。</div>
  </section>
</template>

<style scoped lang="scss" src="./AdminSystemPanel.scss"></style>
