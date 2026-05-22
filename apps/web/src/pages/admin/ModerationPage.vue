<script setup lang="ts">
import { computed, ref } from "vue";
import {
  EyeOutlined,
  FlagOutlined,
  HistoryOutlined,
} from "@ant-design/icons-vue";

import { isAdmin } from "@/features/auth/permissions";
import { useCurrentUser } from "@/features/auth/queries";
import {
  auditActionLabel,
  flagReasonLabel,
  flagStatusLabel,
  reviewableStatusLabel,
  reviewableTypeLabel,
} from "@/features/moderation/model";
import type {
  FlagResponse,
  FlagStatus,
  UserModerationStatus,
  ReviewableResponse,
  ReviewableStatus,
  ReviewableDecisionAction,
} from "@/features/moderation/model";
import {
  useAuditLogs,
  useContentModerationMutation,
  useFlagStatusMutation,
  useModerationQueue,
  useUserStatusMutation,
  useReviewableQueue,
  useClaimReviewableMutation,
  useReleaseReviewableMutation,
  useReviewableDecisionMutation,
} from "@/features/moderation/queries";
import { hasAccessToken } from "@/shared/api/client";
import { relativeTime } from "@/shared/lib/format";
import { topicDetailRoute } from "@/shared/router/topicRoutes";
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";

const activeTab = ref<"reviewables" | "flags" | "audit">("reviewables");

// Flag filter & query
const statusFilter = ref<FlagStatus | "all">("pending");
const selectedQueueStatus = computed<FlagStatus | undefined>(() =>
  statusFilter.value === "all" ? undefined : statusFilter.value,
);
const queueQuery = useModerationQueue(selectedQueueStatus);

// Reviewable filter & query
const reviewableStatusFilter = ref<ReviewableStatus | "all">("pending");
const reviewablesQuery = useReviewableQueue(reviewableStatusFilter);

const auditQuery = useAuditLogs();
const flagStatusMutation = useFlagStatusMutation();
const contentMutation = useContentModerationMutation();
const userStatusMutation = useUserStatusMutation();
const currentUserQuery = useCurrentUser();

const claimMutation = useClaimReviewableMutation();
const releaseMutation = useReleaseReviewableMutation();
const decisionMutation = useReviewableDecisionMutation();

const userId = ref("");
const userStatus = ref<UserModerationStatus>("silenced");
const userNote = ref("");
const hasToken = computed(() => hasAccessToken());
const canUpdateUserStatus = computed(() => isAdmin(currentUserQuery.data.value));
const currentUserId = computed(() => currentUserQuery.data.value?.id);

const flags = computed(() => queueQuery.data.value ?? []);
const reviewables = computed(() => reviewablesQuery.data.value ?? []);
const auditLogs = computed(() => auditQuery.data.value ?? []);

const queueError = computed(() =>
  queueQuery.isError.value ||
  reviewablesQuery.isError.value ||
  auditQuery.isError.value,
);

const pendingAction = computed(
  () =>
    flagStatusMutation.isPending.value ||
    contentMutation.isPending.value ||
    userStatusMutation.isPending.value ||
    claimMutation.isPending.value ||
    releaseMutation.isPending.value ||
    decisionMutation.isPending.value,
);

// Drawer state
const selectedReviewable = ref<ReviewableResponse | null>(null);
const isDrawerOpen = computed(() => selectedReviewable.value !== null);
const decisionAction = ref<ReviewableDecisionAction>("approve");
const decisionNote = ref("");

function openReviewableDetails(reviewable: ReviewableResponse) {
  selectedReviewable.value = reviewable;
  decisionAction.value = "approve";
  decisionNote.value = "";
}

function closeDrawer() {
  selectedReviewable.value = null;
}

function submitDecision() {
  if (!selectedReviewable.value) return;
  decisionMutation.mutate(
    {
      reviewableId: selectedReviewable.value.id,
      payload: {
        action: decisionAction.value,
        note: decisionNote.value.trim() || null,
      },
    },
    {
      onSuccess: () => {
        closeDrawer();
      },
    },
  );
}

function handleClaim(reviewableId: string) {
  claimMutation.mutate(reviewableId);
}

function handleRelease(reviewableId: string) {
  releaseMutation.mutate(reviewableId);
}

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
  return topicDetailRoute({
    id: topicId,
    slug: topicSlug,
    hash: flag.target.post_number ? `post-${flag.target.post_number}` : null,
  });
}
</script>

<template>
  <div class="moderation-page">
    <section class="moderation-hero" aria-labelledby="moderation-title">
      <div>
        <span class="panel-kicker">Safety Console</span>
        <h1 id="moderation-title">审核与社区安全</h1>
        <p>集中处理举报、审核待审内容、查看审计日志，并为管理员提供基础用户状态调整。</p>
      </div>
      <RouterLink class="hero-link" to="/boards">返回社区</RouterLink>
    </section>

    <UiCard v-if="!hasToken" class="moderation-empty">
      <strong>需要登录后才能查看审核台</strong>
      <span>请使用拥有版主、版主所有者或管理员权限的账号访问。</span>
    </UiCard>

    <UiCard v-else-if="queueError" class="moderation-empty">
      <strong>没有审核权限或服务暂不可用</strong>
      <span>普通用户可以举报内容，但不能查看审核队列或审计日志。</span>
    </UiCard>

    <template v-else>
      <!-- Navigation Tabs -->
      <nav class="moderation-tabs" aria-label="审核台导航">
        <button :class="{ active: activeTab === 'reviewables' }" @click="activeTab = 'reviewables'">
          <EyeOutlined /> 审核队列
        </button>
        <button :class="{ active: activeTab === 'flags' }" @click="activeTab = 'flags'">
          <FlagOutlined /> 举报队列
        </button>
        <button :class="{ active: activeTab === 'audit' }" @click="activeTab = 'audit'">
          <HistoryOutlined /> 操作审计
        </button>
      </nav>

      <section class="moderation-layout">
        <!-- Main Column -->
        <main class="queue-column">
          <!-- Tab 1: Reviewables -->
          <div v-if="activeTab === 'reviewables'">
            <div class="section-toolbar">
              <div>
                <span class="panel-kicker">Reviewables queue</span>
                <h2>待审内容队列</h2>
              </div>
              <label>
                <span>状态筛选</span>
                <select v-model="reviewableStatusFilter">
                  <option value="pending">待处理</option>
                  <option value="claimed">已认领</option>
                  <option value="approved">已通过</option>
                  <option value="rejected">已拒绝</option>
                  <option value="hidden">已隐藏</option>
                  <option value="deleted">已删除</option>
                  <option value="silenced">已禁言</option>
                  <option value="escalated">已升级</option>
                  <option value="appealed">申诉中</option>
                  <option value="all">全部</option>
                </select>
              </label>
            </div>

            <div v-if="reviewables.length" class="flag-list">
              <article v-for="rev in reviewables" :key="rev.id" class="flag-card reviewable-card">
                <header>
                  <div>
                    <span class="flag-meta">
                      {{ reviewableTypeLabel(rev.type) }} · {{ reviewableStatusLabel(rev.status) }} ·
                      {{ relativeTime(rev.created_at) }}
                    </span>
                    <h3>{{ rev.data.title || rev.source_summary }}</h3>
                  </div>
                  <button class="detail-link-btn" @click="openReviewableDetails(rev)">
                    查看详情与处理
                  </button>
                </header>

                <p class="reviewable-excerpt">{{ rev.source_summary || rev.data.raw_md || '无正文内容' }}</p>

                <dl>
                  <div>
                    <dt>来源类型</dt>
                    <dd>{{ reviewableTypeLabel(rev.type) }}</dd>
                  </div>
                  <div>
                    <dt>发帖用户</dt>
                    <dd>{{ rev.target_user_name || rev.created_by_name || '系统' }}</dd>
                  </div>
                  <div>
                    <dt>所属版块</dt>
                    <dd>{{ rev.board_name || '全局' }}</dd>
                  </div>
                  <div>
                    <dt>认领人</dt>
                    <dd>{{ rev.assigned_to_name || '未认领' }}</dd>
                  </div>
                </dl>

                <footer>
                  <!-- Claim/Release Actions -->
                  <div class="footer-actions">
                    <template v-if="rev.status === 'pending' || rev.status === 'appealed'">
                      <UiButton tone="success" :disabled="pendingAction" @click="handleClaim(rev.id)">
                        认领任务
                      </UiButton>
                    </template>
                    <template v-else-if="rev.status === 'claimed'">
                      <template v-if="rev.assigned_to_id === currentUserId">
                        <UiButton tone="subtle" :disabled="pendingAction" @click="handleRelease(rev.id)">
                          释放任务
                        </UiButton>
                        <UiButton tone="success" :disabled="pendingAction" @click="openReviewableDetails(rev)">
                          立即处理
                        </UiButton>
                      </template>
                      <template v-else>
                        <span class="assignee-warn">已由 {{ rev.assigned_to_name }} 认领</span>
                      </template>
                    </template>
                    <template v-else>
                      <span class="resolved-note">处理人: {{ rev.resolved_by_name || '系统' }}</span>
                    </template>
                  </div>
                </footer>
              </article>
            </div>

            <UiCard v-else class="moderation-empty">
              <strong>当前筛选下没有审核任务</strong>
              <span>满足敏感规则的内容或被限制的用户发帖将在此等待审核。</span>
            </UiCard>
          </div>

          <!-- Tab 2: Flags -->
          <div v-if="activeTab === 'flags'">
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
                  <RouterLink :to="targetRoute(flag)">
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
          </div>

          <!-- Tab 3: Audit Logs -->
          <div v-if="activeTab === 'audit'">
            <div class="section-toolbar">
              <div>
                <span class="panel-kicker">Audit log</span>
                <h2>全站审计日志</h2>
              </div>
            </div>

            <UiCard class="audit-panel main-audit-panel">
              <ol v-if="auditLogs.length">
                <li v-for="log in auditLogs" :key="log.id" class="audit-log-item">
                  <div class="log-meta">
                    <strong>{{ auditActionLabel(log.action) }}</strong>
                    <span class="log-time">{{ relativeTime(log.created_at) }}</span>
                  </div>
                  <div class="log-desc">
                    操作人: <span>{{ log.actor_name || "系统" }}</span> ·
                    目标类型: <span>{{ log.target_type }}</span> ·
                    目标 ID: <span>{{ log.target_id }}</span>
                    <span v-if="log.data && Object.keys(log.data).length" class="log-details-block">
                      <br />详情: <code class="log-data-code">{{ JSON.stringify(log.data) }}</code>
                    </span>
                  </div>
                </li>
              </ol>
              <p v-else>暂无审计记录。</p>
            </UiCard>
          </div>
        </main>

        <!-- Sidebar Column (User Management, quick stats) -->
        <aside class="side-column" aria-label="管理工具">
          <UiCard v-if="canUpdateUserStatus" class="user-tool">
            <span class="panel-kicker">Admin action</span>
            <h2>用户状态调整</h2>
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

          <UiCard v-else class="user-tool">
            <span class="panel-kicker">Admin action</span>
            <h2>用户状态</h2>
            <p>只有全站管理员可以调整用户状态；版主可以处理举报、审核队列和内容可见性。</p>
          </UiCard>

          <UiCard v-if="activeTab !== 'audit'" class="audit-panel mini-audit-panel">
            <span class="panel-kicker">Audit log</span>
            <h2>最近审计</h2>
            <ol v-if="auditLogs.length">
              <li v-for="log in auditLogs.slice(0, 5)" :key="log.id">
                <strong>{{ auditActionLabel(log.action) }}</strong>
                <span>{{ log.actor_name || "系统" }} · {{ relativeTime(log.created_at) }}</span>
              </li>
            </ol>
            <p v-else>暂无审计记录。</p>
          </UiCard>
        </aside>
      </section>
    </template>

    <!-- Details Drawer Overlay -->
    <div class="drawer-overlay" :class="{ 'drawer-overlay--open': isDrawerOpen }" @click="closeDrawer">
      <div class="drawer-panel" :class="{ 'drawer-panel--open': isDrawerOpen }" @click.stop>
        <!-- Header -->
        <header class="drawer-header">
          <h3>审核任务详情</h3>
          <button class="close-btn" @click="closeDrawer">&times;</button>
        </header>

        <!-- Body -->
        <div class="drawer-body" v-if="selectedReviewable">
          <div class="drawer-section">
            <span class="panel-kicker">Metadata</span>
            <div class="meta-grid">
              <div><strong>类型:</strong> {{ reviewableTypeLabel(selectedReviewable.type) }}</div>
              <div><strong>状态:</strong> {{ reviewableStatusLabel(selectedReviewable.status) }}</div>
              <div><strong>时间:</strong> {{ relativeTime(selectedReviewable.created_at) }}</div>
              <div><strong>版块:</strong> {{ selectedReviewable.board_name || '全局' }}</div>
              <div><strong>创建者:</strong> {{ selectedReviewable.created_by_name || '系统' }}</div>
              <div><strong>认领人:</strong> {{ selectedReviewable.assigned_to_name || '暂无' }}</div>
            </div>
          </div>

          <div class="drawer-section content-preview">
            <span class="panel-kicker">Content Preview</span>
            <h4 class="preview-title" v-if="selectedReviewable.data.title">{{ selectedReviewable.data.title }}</h4>
            <div class="preview-body-box">
              <p v-if="selectedReviewable.data.raw_md" class="raw-markdown-view">{{ selectedReviewable.data.raw_md }}</p>
              <p v-else class="source-summary-view">{{ selectedReviewable.source_summary || '（无具体正文，仅包含元数据或已隐藏）' }}</p>
            </div>
            <div class="content-appeal-note" v-if="selectedReviewable.data.appeal_reason || selectedReviewable.data.note">
              <strong>申诉理由 / 备注:</strong> {{ selectedReviewable.data.appeal_reason || selectedReviewable.data.note }}
            </div>
          </div>

          <!-- History Events -->
          <div class="drawer-section event-history-section">
            <span class="panel-kicker">Workflow History</span>
            <div v-if="selectedReviewable.events && selectedReviewable.events.length" class="drawer-events-list">
              <div v-for="event in selectedReviewable.events" :key="event.id" class="drawer-event-item">
                <div class="event-meta">
                  <strong>{{ auditActionLabel(event.event) }}</strong>
                  <span class="event-time">{{ relativeTime(event.created_at) }}</span>
                </div>
                <div class="event-desc">
                  执行人: <span>{{ event.actor_name || '系统' }}</span>
                  <span v-if="event.from_status || event.to_status">
                    （{{ reviewableStatusLabel(event.from_status || '') }} &rarr; {{ reviewableStatusLabel(event.to_status || '') }}）
                  </span>
                </div>
                <div v-if="event.note" class="event-note-quote">“{{ event.note }}”</div>
              </div>
            </div>
            <p v-else class="no-events-desc">暂无工作流事件流。</p>
          </div>

          <!-- Operations Form (only if claimed by current user, or user is admin and wants to decide) -->
          <div class="drawer-section operations-form" v-if="selectedReviewable.status === 'claimed' && selectedReviewable.assigned_to_id === currentUserId">
            <span class="panel-kicker">Moderator Decision</span>
            <label class="form-label">
              <span>处理动作</span>
              <select v-model="decisionAction">
                <option value="approve">通过发布 (Approve)</option>
                <option value="reject">拒绝并驳回 (Reject)</option>
                <option value="hide">隐藏内容 (Hide)</option>
                <option value="delete">彻底删除 (Delete)</option>
                <option value="silence">禁言作者 (Silence Author)</option>
                <option value="escalate">升级审核 (Escalate)</option>
              </select>
            </label>
            <label class="form-label">
              <span>处理备注 / 决议理由</span>
              <textarea v-model="decisionNote" rows="3" placeholder="写下处理原因（会通知该用户并记入审计）" />
            </label>
            <div class="form-actions">
              <UiButton tone="success" :disabled="pendingAction" @click="submitDecision">提交处理决定</UiButton>
              <UiButton tone="subtle" :disabled="pendingAction" @click="handleRelease(selectedReviewable.id)">释放认领</UiButton>
            </div>
          </div>
          <div class="drawer-section operations-form-readonly" v-else-if="selectedReviewable.status === 'claimed'">
            <span class="panel-kicker">Moderator Decision</span>
            <p class="action-locked-desc">此任务当前已被 <strong>{{ selectedReviewable.assigned_to_name }}</strong> 认领。您需要先认领此任务才能提交处理决定。</p>
          </div>
          <div class="drawer-section operations-form-readonly" v-else-if="selectedReviewable.status === 'pending' || selectedReviewable.status === 'appealed'">
            <span class="panel-kicker">Moderator Decision</span>
            <p class="action-locked-desc">此任务处于 <strong>{{ reviewableStatusLabel(selectedReviewable.status) }}</strong> 状态。认领后即可在此进行审批处理。</p>
            <UiButton tone="success" :disabled="pendingAction" @click="handleClaim(selectedReviewable.id)">认领任务</UiButton>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss" src="./ModerationPage.scss"></style>
