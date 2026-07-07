<script setup lang="ts">
import { computed } from "vue";

import type { AdminSystemOverviewResponse } from "@/features/admin/model";
import { useAdminSystem } from "@/features/admin/queries";
import { relativeTime } from "@/shared/lib/format";
import UiBadge from "@/shared/ui/Badge.vue";
import UiCard from "@/shared/ui/Card.vue";

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
const statCards = computed(() => {
  const stats: AdminSystemOverviewResponse["stats"] | undefined = system.value?.stats;
  if (!stats) {
    return [];
  }
  return [
    { label: "用户", value: stats.users },
    { label: "版块", value: stats.boards },
    { label: "主题", value: stats.topics },
    { label: "楼层", value: stats.posts },
    { label: "待处理举报", value: stats.pending_flags },
    { label: "审计记录", value: stats.audit_logs },
  ];
});
const recentErrorSummaries = computed(() => summarizeRecentErrors(system.value?.recent_errors ?? []));

// Maps backend service identifiers to labels used in the admin dashboard.
// Key parameter `name` is the API service id. Return value is a Chinese display label; side effect: none.
function serviceNameLabel(name: string): string {
  const labels: Record<string, string> = {
    cache: "缓存",
    database: "数据库",
    mail: "邮件",
    workers: "任务",
  };
  return labels[name] ?? name;
}

// Maps backend service status values to short dashboard labels.
// Key parameter `status` is the API status value. Return value is display text; side effect: none.
function serviceStatusLabel(status: string): string {
  if (status === "ok") {
    return "正常";
  }
  if (status === "degraded") {
    return "异常";
  }
  return "未知";
}

// Returns a compact class suffix for service status styling.
// Key parameter `status` is the API status value. Return value is a stable class suffix; side effect: none.
function serviceStatusClass(status: string): string {
  if (status === "ok") {
    return "ok";
  }
  if (status === "degraded") {
    return "degraded";
  }
  return "unknown";
}

function serviceTone(status: string): "green" | "amber" | "gray" {
  if (status === "ok") {
    return "green";
  }
  if (status === "degraded") {
    return "amber";
  }
  return "gray";
}

// Collapses raw dead-letter rows into operator-friendly task summaries.
// Key parameter `errors` is the `/admin/system` recent_errors payload. Return value is
// grouped Chinese summaries sorted by most recent occurrence; side effect: none.
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

  return Array.from(groups.values()).sort((left, right) =>
    Date.parse(right.lastOccurredAt) - Date.parse(left.lastOccurredAt),
  );
}

// Reads an unknown API field as a string while keeping template rendering predictable.
// Key parameter `value` is an untyped API field; `fallback` is returned for absent values.
// Return value is a string; side effect: none.
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
  return "如持续出现，请查看后台任务日志定位具体原因。";
}

// Compares two optional ISO-like timestamp strings for summary ordering.
// Key parameters are display timestamps from the API. Return value is true when `candidate`
// is later than `current`; side effect: none.
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
  <section class="ops-grid" aria-label="系统健康">
    <UiCard class="ops-card ops-card--wide">
      <div class="section-head">
        <div class="title-area">
          <h2>系统面板</h2>
          <span v-if="system" class="system-meta">v{{ system.version }} · {{ system.environment }}</span>
        </div>
      </div>
      <p v-if="systemQuery.isLoading.value" class="panel-state" role="status">正在读取系统状态…</p>
      <p v-else-if="systemQuery.isError.value" class="panel-state panel-state--error" role="alert">
        系统面板暂不可用。
      </p>
      <template v-else-if="system">
        <div class="stat-strip">
          <div v-for="stat in statCards" :key="stat.label" class="stat-pill">
            <span>{{ stat.label }}</span>
            <strong>{{ stat.value }}</strong>
          </div>
        </div>
        <div class="service-grid">
          <article
            v-for="service in system.services"
            :key="service.name"
            :class="`service-card service-card--${serviceStatusClass(service.status)}`"
          >
            <UiBadge :tone="serviceTone(service.status)">{{ serviceStatusLabel(service.status) }}</UiBadge>
            <strong>{{ serviceNameLabel(service.name) }}</strong>
          </article>
        </div>
        <div class="queue-status-section">
          <h3>任务队列</h3>
          <div class="queue-overview">
            <div class="queue-stats">
              <div class="queue-stat-pill">
                <span>待执行</span>
                <strong>{{ system.queue.queued ?? 0 }}</strong>
              </div>
              <div class="queue-stat-pill">
                <span>执行中</span>
                <strong>{{ system.queue.running ?? 0 }}</strong>
              </div>
              <div class="queue-stat-pill">
                <span>失败</span>
                <strong :class="{ 'has-dead': (system.queue.dead ?? 0) > 0 }">{{ system.queue.dead ?? 0 }}</strong>
              </div>
            </div>
          </div>
        </div>
      </template>
    </UiCard>

    <UiCard class="ops-card">
      <div class="section-head">
        <div class="title-area">
          <h2>邮件日志</h2>
        </div>
      </div>
      <ol v-if="system?.recent_email_logs.length" class="compact-list">
        <li v-for="email in system.recent_email_logs" :key="`${email.kind}-${email.sent_at}`">
          <strong>{{ email.subject }}</strong>
          <span>{{ email.to_email }} · {{ relativeTime(email.sent_at) }}</span>
        </li>
      </ol>
      <p v-else class="panel-state">暂无邮件记录。</p>
    </UiCard>
  </section>

  <div v-if="system" class="log-grid">
    <UiCard class="audit-card">
      <div class="section-head">
        <div class="title-area">
          <h2>最近审计</h2>
        </div>
      </div>
      <ol v-if="system.recent_audit_logs.length" class="audit-timeline">
        <li v-for="log in system.recent_audit_logs" :key="log.id">
          <strong>{{ log.action }}</strong>
          <span>{{ log.actor_name || "系统" }} · {{ log.target_type }} · {{ relativeTime(log.created_at) }}</span>
        </li>
      </ol>
      <p v-else class="panel-state">暂无审计记录。</p>
    </UiCard>

    <UiCard class="error-card">
      <div class="section-head">
        <div class="title-area">
          <h2>任务提醒</h2>
        </div>
      </div>
      <ol v-if="recentErrorSummaries.length" class="task-alert-list">
        <li v-for="error in recentErrorSummaries" :key="error.key" class="task-alert">
          <div class="task-alert__header">
            <strong>{{ error.taskLabel }}</strong>
            <div>
              <UiBadge tone="amber">{{ error.count }} 次</UiBadge>
              <span v-if="error.lastOccurredAt" class="error-time">
                最近 {{ relativeTime(error.lastOccurredAt) }}
              </span>
            </div>
          </div>
          <p>{{ error.message }}</p>
          <span>{{ error.action }}</span>
        </li>
      </ol>
      <p v-else class="panel-state">后台任务运行正常。</p>
    </UiCard>
  </div>
</template>

<style scoped lang="scss" src="./AdminSystemPanel.scss"></style>
