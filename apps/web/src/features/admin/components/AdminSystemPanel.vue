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
        <span class="panel-kicker">System</span>
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
          <article v-for="service in system.services" :key="service.name" class="service-card">
            <UiBadge :tone="serviceTone(service.status)">{{ service.status }}</UiBadge>
            <strong>{{ service.name }}</strong>
            <span>{{ service.detail }}</span>
          </article>
        </div>
        <div class="queue-status-section">
          <h3>后台队列与调度</h3>
          <div class="queue-overview">
            <div class="queue-stats">
              <div class="queue-stat-pill">
                <span>排队中</span>
                <strong>{{ system.queue.queued ?? 0 }}</strong>
              </div>
              <div class="queue-stat-pill">
                <span>执行中</span>
                <strong>{{ system.queue.running ?? 0 }}</strong>
              </div>
              <div class="queue-stat-pill">
                <span>已失效 (Dead)</span>
                <strong :class="{ 'has-dead': (system.queue.dead ?? 0) > 0 }">{{ system.queue.dead ?? 0 }}</strong>
              </div>
            </div>
            <div class="queue-config-grid">
              <div class="config-item">
                <span class="config-label">Worker 模块</span>
                <span class="config-value">{{ system.queue.worker }}</span>
              </div>
              <div class="config-item">
                <span class="config-label">轮询间隔 / 批次</span>
                <span class="config-value">{{ system.queue.poll_seconds }}s / {{ system.queue.batch_size }}条</span>
              </div>
              <div class="config-item">
                <span class="config-label">热度排行调度</span>
                <span class="config-value">每 {{ system.queue.hot_rank_interval_seconds }}s</span>
              </div>
              <div class="config-item">
                <span class="config-label">上传清理调度</span>
                <span class="config-value">每 {{ system.queue.upload_cleanup_interval_seconds }}s</span>
              </div>
              <div class="config-item">
                <span class="config-label">热点资讯采集</span>
                <span class="config-value">每 {{ system.queue.frontier_news_interval_seconds ?? 0 }}s</span>
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
        <span class="panel-kicker">Mail</span>
      </div>
      <ol v-if="system?.recent_email_logs.length" class="compact-list">
        <li v-for="email in system.recent_email_logs" :key="`${email.kind}-${email.sent_at}`">
          <strong>{{ email.subject }}</strong>
          <span>{{ email.to_email }} · {{ relativeTime(email.sent_at) }}</span>
        </li>
      </ol>
      <p v-else class="panel-state">暂无本地邮件记录。</p>
    </UiCard>
  </section>

  <div v-if="system" class="log-grid">
    <UiCard class="audit-card">
      <div class="section-head">
        <div class="title-area">
          <h2>最近审计</h2>
        </div>
        <span class="panel-kicker">Audit</span>
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
        <span class="panel-kicker">Errors</span>
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
