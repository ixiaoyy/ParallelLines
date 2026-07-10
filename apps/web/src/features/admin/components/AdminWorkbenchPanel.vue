<script setup lang="ts">
import {
  AlertOutlined,
  ArrowRightOutlined,
  AuditOutlined,
  BarChartOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  ExclamationCircleOutlined,
  FlagOutlined,
  SafetyCertificateOutlined,
  SettingOutlined,
  TeamOutlined,
} from "@ant-design/icons-vue";
import { computed } from "vue";

import { useAdminSystem } from "@/features/admin/queries";
import { relativeTime } from "@/shared/lib/format";
import UiButton from "@/shared/ui/Button.vue";

const systemQuery = useAdminSystem();
const system = computed(() => systemQuery.data.value);
const todayLabel = new Intl.DateTimeFormat("zh-CN", {
  year: "numeric",
  month: "long",
  day: "numeric",
  weekday: "long",
}).format(new Date());

const quickLinks = [
  {
    label: "查看增长数据",
    description: "访问、访客与真实用户增长",
    icon: BarChartOutlined,
    route: "admin-analytics",
  },
  {
    label: "管理用户",
    description: "账号状态、角色与成长信息",
    icon: TeamOutlined,
    route: "admin-users",
  },
  {
    label: "处理审核",
    description: "内容举报与审核队列",
    icon: AuditOutlined,
    route: "admin-moderation",
  },
  {
    label: "检查系统",
    description: "服务、任务队列与运行日志",
    icon: SettingOutlined,
    route: "admin-system",
  },
] as const;

const summaryItems = computed(() => {
  const stats = system.value?.stats;
  const queue = system.value?.queue;
  if (!stats || !queue) {
    return [];
  }
  return [
    {
      label: "待处理举报",
      value: stats.pending_flags,
      note: stats.pending_flags > 0 ? "进入审核台处理" : "当前没有待处理项",
      icon: FlagOutlined,
      route: "admin-moderation",
      tone: stats.pending_flags > 0 ? "warning" : "success",
    },
    {
      label: "社区用户",
      value: stats.users,
      note: "当前用户总数",
      icon: TeamOutlined,
      route: "admin-users",
      tone: "info",
    },
    {
      label: "主题与回复",
      value: stats.topics + stats.posts,
      note: `${stats.topics} 个主题 · ${stats.posts} 条回复`,
      icon: AuditOutlined,
      route: "admin-analytics",
      tone: "info",
    },
    {
      label: "失败任务",
      value: queue.dead ?? 0,
      note: (queue.dead ?? 0) > 0 ? "查看失败记录" : "任务队列运行正常",
      icon: SafetyCertificateOutlined,
      route: "admin-system",
      tone: (queue.dead ?? 0) > 0 ? "danger" : "success",
    },
  ];
});

const attentionItems = computed(() => {
  if (!system.value) {
    return [];
  }
  const items: Array<{
    key: string;
    title: string;
    detail: string;
    route: "admin-moderation" | "admin-system";
    tone: "warning" | "danger";
  }> = [];

  if (system.value.stats.pending_flags > 0) {
    items.push({
      key: "pending-flags",
      title: `${system.value.stats.pending_flags} 条举报等待处理`,
      detail: "进入审核台查看举报内容与处理记录。",
      route: "admin-moderation",
      tone: "warning",
    });
  }

  const degradedServices = system.value.services.filter((service) => service.status !== "ok");
  for (const service of degradedServices) {
    items.push({
      key: `service-${service.name}`,
      title: `${serviceNameLabel(service.name)}服务需要留意`,
      detail: service.detail || "服务未返回更多状态说明。",
      route: "admin-system",
      tone: service.status === "degraded" ? "danger" : "warning",
    });
  }

  if ((system.value.queue.dead ?? 0) > 0) {
    items.push({
      key: "dead-jobs",
      title: `${system.value.queue.dead} 个后台任务执行失败`,
      detail: "失败任务会保留在系统运行记录中，请检查错误摘要。",
      route: "admin-system",
      tone: "danger",
    });
  }

  return items.slice(0, 4);
});

const recentAuditLogs = computed(() => system.value?.recent_audit_logs.slice(0, 6) ?? []);

// Maps backend service identifiers to the operator-facing labels used on the workbench.
// Key parameter `name` is the service id from `/admin/system`. Return value is localized text; side effect: none.
function serviceNameLabel(name: string): string {
  const labels: Record<string, string> = {
    cache: "缓存",
    database: "数据库",
    mail: "邮件",
    workers: "后台任务",
  };
  return labels[name] ?? name;
}

// Converts audit target identifiers into concise activity descriptions without fabricating entity names.
// Key parameters are raw target type/id fields. Return value is display text; side effect: none.
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
</script>

<template>
  <div class="admin-dashboard-page">
    <header class="admin-page-header">
      <div>
        <span class="admin-page-context">运营总览</span>
        <h1>工作台</h1>
        <p>集中查看社区状态，处理今天最重要的运营事项。</p>
      </div>
      <div class="admin-page-date">
        <ClockCircleOutlined aria-hidden="true" />
        <span>{{ todayLabel }}</span>
      </div>
    </header>

    <div v-if="systemQuery.isLoading.value" class="admin-dashboard-skeleton" role="status">
      <span class="sr-only">运营数据加载中…</span>
      <i v-for="index in 8" :key="index" />
    </div>

    <section v-else-if="systemQuery.isError.value" class="admin-inline-error" role="alert">
      <ExclamationCircleOutlined aria-hidden="true" />
      <div>
        <strong>运营数据暂时无法加载</strong>
        <p>权限已确认，但系统概览请求失败。请检查网络后重试。</p>
      </div>
      <UiButton tone="subtle" :disabled="systemQuery.isFetching.value" @click="systemQuery.refetch()">
        {{ systemQuery.isFetching.value ? "重试中…" : "重新加载" }}
      </UiButton>
    </section>

    <template v-else-if="system">
      <section class="admin-summary-strip" aria-label="运营摘要">
        <RouterLink
          v-for="item in summaryItems"
          :key="item.label"
          class="admin-summary-item"
          :class="`is-${item.tone}`"
          :to="{ name: item.route }"
        >
          <span>{{ item.label }}</span>
          <span class="admin-summary-item__value">
            <strong>{{ item.value }}</strong>
            <component :is="item.icon" aria-hidden="true" />
          </span>
          <small>{{ item.note }}</small>
        </RouterLink>
      </section>

      <div class="admin-workbench-grid">
        <section class="admin-flat-section" aria-labelledby="workbench-focus-title">
          <header class="admin-section-header">
            <div>
              <span>当前状态</span>
              <h2 id="workbench-focus-title">需要处理</h2>
            </div>
            <strong>{{ attentionItems.length }} 项</strong>
          </header>

          <div v-if="attentionItems.length" class="admin-attention-list">
            <RouterLink
              v-for="item in attentionItems"
              :key="item.key"
              class="admin-attention-item"
              :class="`is-${item.tone}`"
              :to="{ name: item.route }"
            >
              <span class="admin-attention-item__icon">
                <AlertOutlined v-if="item.tone === 'warning'" aria-hidden="true" />
                <ExclamationCircleOutlined v-else aria-hidden="true" />
              </span>
              <span>
                <strong>{{ item.title }}</strong>
                <small>{{ item.detail }}</small>
              </span>
              <ArrowRightOutlined aria-hidden="true" />
            </RouterLink>
          </div>
          <div v-else class="admin-healthy-state">
            <CheckCircleOutlined aria-hidden="true" />
            <span>
              <strong>当前没有需要立即处理的异常</strong>
              <small>服务、任务队列与举报统计均未触发提醒。</small>
            </span>
          </div>
        </section>

        <section class="admin-flat-section" aria-labelledby="workbench-activity-title">
          <header class="admin-section-header">
            <div>
              <span>操作记录</span>
              <h2 id="workbench-activity-title">最近管理动态</h2>
            </div>
            <strong>{{ recentAuditLogs.length }} 条</strong>
          </header>

          <ol v-if="recentAuditLogs.length" class="admin-activity-list">
            <li v-for="log in recentAuditLogs" :key="log.id">
              <span class="admin-activity-list__status"><CheckCircleOutlined aria-hidden="true" /></span>
              <span>
                <strong>{{ log.actor_name || "系统" }}</strong>
                <small>{{ log.action }} · {{ auditTargetLabel(log.target_type, log.target_id) }}</small>
              </span>
              <time>{{ relativeTime(log.created_at) }}</time>
            </li>
          </ol>
          <div v-else class="admin-quiet-empty">暂无管理操作记录。</div>
        </section>
      </div>

      <section class="admin-flat-section admin-quick-section" aria-labelledby="admin-quick-title">
        <header class="admin-section-header">
          <div>
            <span>常用功能</span>
            <h2 id="admin-quick-title">快捷入口</h2>
          </div>
        </header>
        <nav class="admin-quick-grid" aria-label="后台快捷入口">
          <RouterLink v-for="item in quickLinks" :key="item.route" :to="{ name: item.route }">
            <component :is="item.icon" aria-hidden="true" />
            <span>
              <strong>{{ item.label }}</strong>
              <small>{{ item.description }}</small>
            </span>
            <ArrowRightOutlined aria-hidden="true" />
          </RouterLink>
        </nav>
      </section>
    </template>
  </div>
</template>

<style scoped lang="scss" src="./AdminWorkbenchPanel.scss"></style>
