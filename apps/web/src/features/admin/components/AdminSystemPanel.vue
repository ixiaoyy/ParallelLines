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
    { label: "帖子", value: stats.posts },
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
        <span class="panel-kicker">System</span>
        <h2>系统面板</h2>
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
      </template>
    </UiCard>

    <UiCard class="ops-card">
      <div class="section-head">
        <span class="panel-kicker">Mail</span>
        <h2>邮件日志</h2>
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

  <UiCard class="audit-card">
    <div class="section-head">
      <span class="panel-kicker">Audit</span>
      <h2>最近审计</h2>
    </div>
    <ol v-if="system?.recent_audit_logs.length" class="audit-timeline">
      <li v-for="log in system.recent_audit_logs" :key="log.id">
        <strong>{{ log.action }}</strong>
        <span>{{ log.actor_name || "系统" }} · {{ log.target_type }} · {{ relativeTime(log.created_at) }}</span>
      </li>
    </ol>
    <p v-else class="panel-state">暂无审计记录。</p>
  </UiCard>
</template>

<style scoped lang="scss" src="./AdminSystemPanel.scss"></style>
