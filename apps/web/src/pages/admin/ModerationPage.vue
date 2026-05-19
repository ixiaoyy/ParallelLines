<script setup lang="ts">
import { computed, ref } from "vue";

import {
  auditActionLabel,
  flagReasonLabel,
  flagStatusLabel,
} from "@/features/moderation/model";
import type { FlagResponse, FlagStatus, UserModerationStatus } from "@/features/moderation/model";
import {
  useAuditLogs,
  useContentModerationMutation,
  useFlagStatusMutation,
  useModerationQueue,
  useUserStatusMutation,
} from "@/features/moderation/queries";
import { hasAccessToken } from "@/shared/api/client";
import { relativeTime } from "@/shared/lib/format";
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";

const statusFilter = ref<FlagStatus | "all">("pending");
const selectedQueueStatus = computed<FlagStatus | undefined>(() =>
  statusFilter.value === "all" ? undefined : statusFilter.value,
);
const queueQuery = useModerationQueue(selectedQueueStatus);
const auditQuery = useAuditLogs();
const flagStatusMutation = useFlagStatusMutation();
const contentMutation = useContentModerationMutation();
const userStatusMutation = useUserStatusMutation();

const userId = ref("");
const userStatus = ref<UserModerationStatus>("silenced");
const userNote = ref("");
const hasToken = computed(() => hasAccessToken());
const flags = computed(() => queueQuery.data.value ?? []);
const auditLogs = computed(() => auditQuery.data.value ?? []);
const queueError = computed(() => queueQuery.isError.value || auditQuery.isError.value);
const pendingAction = computed(
  () =>
    flagStatusMutation.isPending.value ||
    contentMutation.isPending.value ||
    userStatusMutation.isPending.value,
);

function resolveFlag(flag: FlagResponse) {
  flagStatusMutation.mutate({
    flagId: flag.id,
    payload: { status: "resolved", resolution_note: "已由审核台处理。" },
  });
}

function rejectFlag(flag: FlagResponse) {
  flagStatusMutation.mutate({
    flagId: flag.id,
    payload: { status: "rejected", resolution_note: "未发现违规或证据不足。" },
  });
}

function toggleHidden(flag: FlagResponse) {
  contentMutation.mutate({
    targetType: flag.target.target_type,
    targetId: flag.target.target_id,
    hidden: !flag.target.hidden,
    note: flag.target.hidden ? "审核台恢复内容。" : "审核台隐藏内容。",
  });
}

function updateUser() {
  const trimmedUserId = userId.value.trim();
  if (!trimmedUserId) {
    return;
  }

  userStatusMutation.mutate({
    userId: trimmedUserId,
    payload: { status: userStatus.value, note: userNote.value.trim() || null },
  });
}

function targetRoute(flag: FlagResponse) {
  const topicId = flag.target.topic_id ?? flag.target.target_id;
  const topicSlug = flag.target.topic_slug ?? flag.target.board_slug;
  return {
    path: `/t/${topicSlug}/${topicId}`,
    hash: flag.target.post_number ? `#post-${flag.target.post_number}` : "",
  };
}
</script>

<template>
  <div class="moderation-page">
    <section class="moderation-hero" aria-labelledby="moderation-title">
      <div>
        <span class="panel-kicker">Safety Console</span>
        <h1 id="moderation-title">审核与社区安全</h1>
        <p>集中处理举报、隐藏/恢复内容、查看审计日志，并为管理员提供基础用户状态调整。</p>
      </div>
      <RouterLink class="hero-link" to="/boards">返回社区</RouterLink>
    </section>

    <UiCard v-if="!hasToken" class="moderation-empty">
      <strong>需要登录后才能查看审核台</strong>
      <span>请使用拥有版主、版主所有者或管理员权限的账号访问。</span>
    </UiCard>

    <UiCard v-else-if="queueError" class="moderation-empty">
      <strong>没有审核权限或服务暂不可用</strong>
      <span>普通用户可以举报内容，但不能查看举报队列或审计日志。</span>
    </UiCard>

    <template v-else>
      <section class="moderation-layout">
        <main class="queue-column" aria-label="举报队列">
          <div class="section-toolbar">
            <div>
              <span class="panel-kicker">Flag queue</span>
              <h2>举报队列</h2>
            </div>
            <label>
              <span>状态</span>
              <select v-model="statusFilter">
                <option value="pending">待处理</option>
                <option value="resolved">已处理</option>
                <option value="rejected">已驳回</option>
                <option value="all">全部</option>
              </select>
            </label>
          </div>

          <div v-if="flags.length" class="flag-list">
            <article v-for="flag in flags" :key="flag.id" class="flag-card">
              <header>
                <div>
                  <span class="flag-meta">
                    {{ flagReasonLabel(flag.reason) }} · {{ flagStatusLabel(flag.status) }} ·
                    {{ relativeTime(flag.created_at) }}
                  </span>
                  <h3>{{ flag.target.title }}</h3>
                </div>
                <RouterLink
                  :to="targetRoute(flag)"
                >
                  查看上下文
                </RouterLink>
              </header>

              <p>{{ flag.detail || flag.target.excerpt }}</p>
              <dl>
                <div>
                  <dt>举报人</dt>
                  <dd>{{ flag.reporter_name }}</dd>
                </div>
                <div>
                  <dt>作者</dt>
                  <dd>{{ flag.target.author_name }}</dd>
                </div>
                <div>
                  <dt>版块</dt>
                  <dd>{{ flag.target.board_name }}</dd>
                </div>
                <div>
                  <dt>可见性</dt>
                  <dd>{{ flag.target.hidden ? "已隐藏" : "公开" }}</dd>
                </div>
              </dl>

              <footer>
                <UiButton tone="subtle" :disabled="pendingAction" @click="toggleHidden(flag)">
                  {{ flag.target.hidden ? "恢复内容" : "隐藏内容" }}
                </UiButton>
                <UiButton tone="success" :disabled="pendingAction" @click="resolveFlag(flag)">标记已处理</UiButton>
                <UiButton tone="ghost" :disabled="pendingAction" @click="rejectFlag(flag)">驳回举报</UiButton>
              </footer>
            </article>
          </div>

          <UiCard v-else class="moderation-empty">
            <strong>当前筛选下没有举报</strong>
            <span>用户从主题或楼层操作发起的举报会进入这里。</span>
          </UiCard>
        </main>

        <aside class="side-column" aria-label="管理工具">
          <UiCard class="user-tool">
            <span class="panel-kicker">Admin action</span>
            <h2>用户状态</h2>
            <label>
              <span>用户 ID</span>
              <input v-model="userId" type="text" placeholder="粘贴 user_id" />
            </label>
            <label>
              <span>状态</span>
              <select v-model="userStatus">
                <option value="silenced">禁言</option>
                <option value="suspended">停用</option>
                <option value="active">恢复 active</option>
              </select>
            </label>
            <label>
              <span>备注</span>
              <textarea v-model="userNote" rows="3" placeholder="记录调整原因" />
            </label>
            <UiButton :disabled="pendingAction || !userId.trim()" @click="updateUser">更新用户状态</UiButton>
          </UiCard>

          <UiCard class="audit-panel">
            <span class="panel-kicker">Audit log</span>
            <h2>最近审计</h2>
            <ol v-if="auditLogs.length">
              <li v-for="log in auditLogs" :key="log.id">
                <strong>{{ auditActionLabel(log.action) }}</strong>
                <span>{{ log.actor_name || "系统" }} · {{ relativeTime(log.created_at) }}</span>
              </li>
            </ol>
            <p v-else>暂无审计记录。</p>
          </UiCard>
        </aside>
      </section>
    </template>
  </div>
</template>

<style scoped lang="scss" src="./ModerationPage.scss"></style>
