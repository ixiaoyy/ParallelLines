<script setup lang="ts">
import { computed } from "vue";

import type { AdminSystemOverviewResponse } from "@/features/admin/model";
import { useAdminSystem } from "@/features/admin/queries";
import { relativeTime } from "@/shared/lib/format";
import UiBadge from "@/shared/ui/Badge.vue";
import UiCard from "@/shared/ui/Card.vue";

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
          <h2>最近错误</h2>
        </div>
      </div>
      <ol v-if="system.recent_errors.length" class="compact-list">
        <li v-for="err in system.recent_errors" :key="String(err.id)">
          <div class="error-header">
            <strong>{{ err.task_name }}</strong>
            <span class="error-time">{{ relativeTime(String(err.occurred_at)) }}</span>
          </div>
          <pre class="error-detail">{{ err.error }}</pre>
        </li>
      </ol>
      <p v-else class="panel-state">暂无关键错误。</p>
    </UiCard>
  </div>
</template>

<style scoped lang="scss" src="./AdminSystemPanel.scss"></style>
