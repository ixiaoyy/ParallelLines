<script setup lang="ts">
import {
  ArrowLeftOutlined,
  CheckCircleOutlined,
  SearchOutlined,
  SafetyCertificateOutlined,
  TeamOutlined,
} from "@ant-design/icons-vue";
import { computed, nextTick, reactive, ref, watch } from "vue";

import type { PersonaKind } from "@/entities/user/model";
import OperatorIdentityBadge from "@/features/users/components/OperatorIdentityBadge.vue";
import { normalizePersonaKind, operatorIdentity, OPERATOR_IDENTITIES } from "@/features/users/operatorIdentity";
import type { UserBadgeResponse } from "@/features/badges/model";
import { adminRoleLabel, adminStatusLabel } from "@/features/admin/model";
import type { AdminUserResponse, AdminUserUpdateRequest } from "@/features/admin/model";
import {
  useAdminBadges,
  useAdminUsers,
  useGrantAdminUserBadge,
  useRevokeAdminUserBadge,
  useUpdateAdminUser,
} from "@/features/admin/queries";
import { relativeTime } from "@/shared/lib/format";
import UiAvatar from "@/shared/ui/Avatar.vue";
import UiButton from "@/shared/ui/Button.vue";

type EditableUserStatus = NonNullable<AdminUserUpdateRequest["status"]>;

const updateUserMutation = useUpdateAdminUser();
const grantBadgeMutation = useGrantAdminUserBadge();
const revokeBadgeMutation = useRevokeAdminUserBadge();
const userFilters = reactive({
  query: "",
  role: "",
  status: "",
  accountType: "" as "" | "member" | "persona",
});
const userParams = computed(() => ({
  limit: 50,
  query: userFilters.query.trim() || undefined,
  role: userFilters.role || undefined,
  status: userFilters.status || undefined,
  is_persona:
    userFilters.accountType === "" ? undefined : userFilters.accountType === "persona",
}));
const usersQuery = useAdminUsers(userParams);
const badgesQuery = useAdminBadges();
const users = computed(() => usersQuery.data.value ?? []);
const badgeCatalog = computed(() => badgesQuery.data.value?.filter((badge) => badge.active) ?? []);
const usersPanelElement = ref<HTMLElement | null>(null);
const searchInputElement = ref<HTMLInputElement | null>(null);
const detailBackButtonElement = ref<HTMLButtonElement | null>(null);
const selectedUserId = ref<string | null>(null);
const activePanel = ref<"list" | "detail">("list");

// Resolves the selected row without silently replacing a missing selection; a null selection may initialize to the first result.
// Key parameters: none. Return value: the selected admin row or null. Side effect: none.
const selectedUser = computed(() => {
  const matchingUser = users.value.find((user) => user.id === selectedUserId.value);
  if (matchingUser) {
    return matchingUser;
  }
  return selectedUserId.value === null ? (users.value[0] ?? null) : null;
});

const userDraft = reactive({
  role: "user" as "user" | "moderator" | "admin",
  status: "active" as EditableUserStatus,
  isPersona: false,
  personaKind: null as PersonaKind | null,
  level: 0,
  pointsDelta: 0,
  experienceDelta: 0,
  adjustmentReason: "",
});
const badgeDraft = reactive({
  badgeSlug: "",
  note: "",
  revokeReason: "",
});

watch(
  selectedUser,
  (user) => {
    if (!user) {
      const wasShowingDetail = activePanel.value === "detail";
      activePanel.value = "list";
      selectedUserId.value = null;
      if (wasShowingDetail && isCompactUserLayout()) {
        void nextTick(() => {
          usersPanelElement.value?.scrollIntoView({ block: "start" });
          focusUserListTarget();
        });
      }
      return;
    }
    selectedUserId.value = user.id;
    userDraft.role = user.role === "admin" || user.role === "moderator" ? user.role : "user";
    userDraft.status =
      user.status === "pending_verification" ||
      user.status === "silenced" ||
      user.status === "suspended" ||
      user.status === "deleted"
        ? user.status
        : "active";
    userDraft.isPersona = user.is_persona;
    userDraft.personaKind = normalizePersonaKind(user.is_persona, user.persona_kind);
    userDraft.level = user.level;
    userDraft.pointsDelta = 0;
    userDraft.experienceDelta = 0;
    userDraft.adjustmentReason = "";
    badgeDraft.badgeSlug = "";
    badgeDraft.note = "";
    badgeDraft.revokeReason = "";
  },
  { immediate: true },
);

// Clear the draft subtype when the operator flag is disabled; no network or account mutation.
watch(() => userDraft.isPersona, (isPersona) => {
  if (!isPersona) {
    userDraft.personaKind = null;
  }
});

watch(
  badgeCatalog,
  (badges) => {
    if (!badgeDraft.badgeSlug && badges.length > 0) {
      badgeDraft.badgeSlug = badges[0].slug;
    }
  },
  { immediate: true },
);

// Reports whether user management is using the single-pane compact layout.
// Key parameters: none. Return value: true at 1080px or narrower. Side effect: none.
function isCompactUserLayout(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(max-width: 1080px)").matches
  );
}

// Restores keyboard focus inside the compact user list, falling back to search for empty results.
// Key parameters: none. Return value: none. Side effect: moves focus to the active row or search input.
function focusUserListTarget(): void {
  const selectedButton = usersPanelElement.value?.querySelector<HTMLButtonElement>(
    ".user-list button.is-active",
  );
  (selectedButton ?? searchInputElement.value)?.focus({ preventScroll: true });
}

// Selects the user being edited and opens the detail pane on compact layouts.
// Key parameter `user` is the admin user row. Return value: none. Side effect: updates local state, mutation feedback, scrolling, and focus.
function selectUser(user: AdminUserResponse): void {
  if (selectedUserId.value !== user.id) {
    updateUserMutation.reset();
    grantBadgeMutation.reset();
    revokeBadgeMutation.reset();
  }
  selectedUserId.value = user.id;
  activePanel.value = "detail";
  void nextTick(() => {
    usersPanelElement.value?.scrollIntoView({ block: "start" });
    if (isCompactUserLayout()) {
      detailBackButtonElement.value?.focus({ preventScroll: true });
    }
  });
}

// Returns compact user management to the list and restores focus to the selected row.
// Key parameters: none. Return value: none. Side effect: changes the visible pane, scrolls it into view, and moves keyboard focus.
function showUserList(): void {
  activePanel.value = "list";
  if (isCompactUserLayout()) {
    void nextTick(() => {
      usersPanelElement.value?.scrollIntoView({ block: "start" });
      focusUserListTarget();
    });
  }
}

// Sends account classification, permissions, level, and optional growth deltas for the selected user.
// Key parameters: none. Return value: none. Side effect: invokes updateAdminUser and refreshes admin queries on success.
function saveUser(): void {
  if (!selectedUser.value) {
    return;
  }
  const payload: AdminUserUpdateRequest = {
    role: userDraft.role,
    status: userDraft.status,
    is_persona: userDraft.isPersona,
    persona_kind: userDraft.isPersona ? userDraft.personaKind : null,
    level: Number(userDraft.level),
  };
  const pointsDelta = Number(userDraft.pointsDelta);
  const experienceDelta = Number(userDraft.experienceDelta);
  if (pointsDelta !== 0) {
    payload.points_delta = pointsDelta;
  }
  if (experienceDelta !== 0) {
    payload.experience_delta = experienceDelta;
  }
  const reason = userDraft.adjustmentReason.trim();
  if (reason) {
    payload.adjustment_reason = reason;
  }
  updateUserMutation.mutate({
    userId: selectedUser.value.id,
    payload,
  });
}

// Grants the selected catalog badge to the active user through the admin badge mutation.
// Key parameters: none. Return value: none. Side effect: updates the user badge list after invalidation.
function grantBadge(): void {
  if (!selectedUser.value || !badgeDraft.badgeSlug) {
    return;
  }
  grantBadgeMutation.mutate({
    userId: selectedUser.value.id,
    payload: {
      badge_slug: badgeDraft.badgeSlug,
      note: badgeDraft.note.trim() || null,
    },
  });
}

// Revokes one active badge from the selected user and records the administrator's reason.
// Key parameter `badge` is the active badge row. Return value: none. Side effect: invokes the revoke mutation.
function revokeBadge(badge: UserBadgeResponse): void {
  if (!selectedUser.value) {
    return;
  }
  revokeBadgeMutation.mutate({
    userId: selectedUser.value.id,
    badgeSlug: badge.badge_slug,
    payload: {
      reason: badgeDraft.revokeReason.trim() || "管理员手动撤销",
    },
  });
}

// Returns a semantic class for account state pills while preserving unknown backend values.
// Key parameter `status` is the API account state. Return value is a CSS suffix; side effect: none.
function accountStatusClass(status: string): string {
  if (status === "active") {
    return "success";
  }
  if (status === "silenced") {
    return "warning";
  }
  if (status === "suspended" || status === "deleted") {
    return "danger";
  }
  return "neutral";
}
</script>

<template>
  <section
    ref="usersPanelElement"
    class="users-panel"
    :class="{ 'is-showing-detail': activePanel === 'detail' }"
    aria-labelledby="admin-users-title"
  >
    <header class="users-panel__header">
      <div>
        <span class="users-panel__context">成员与权限</span>
        <h1 id="admin-users-title">用户管理</h1>
        <p>查询账号，维护运营/测试归类、角色、状态、积分成长与徽章。</p>
      </div>
      <span v-if="!usersQuery.isLoading.value && !usersQuery.isError.value" class="user-result-count">
        当前显示 <strong>{{ users.length }}</strong> 人
      </span>
    </header>

    <div class="user-toolbar" aria-label="用户筛选">
      <label class="filter-field filter-field--search">
        <span class="filter-field__label">搜索用户</span>
        <span class="search-control">
          <SearchOutlined aria-hidden="true" />
          <input
            ref="searchInputElement"
            v-model="userFilters.query"
            type="search"
            placeholder="搜索用户名或邮箱"
          />
        </span>
      </label>
      <label class="filter-field">
        <span class="filter-field__label">角色</span>
        <select v-model="userFilters.role">
          <option value="">全部角色</option>
          <option value="admin">管理员</option>
          <option value="moderator">版主</option>
          <option value="user">用户</option>
        </select>
      </label>
      <label class="filter-field">
        <span class="filter-field__label">状态</span>
        <select v-model="userFilters.status">
          <option value="">全部状态</option>
          <option value="pending_verification">待验证</option>
          <option value="active">正常</option>
          <option value="silenced">禁言</option>
          <option value="suspended">停用</option>
          <option value="deleted">已删除</option>
        </select>
      </label>
      <label class="filter-field">
        <span class="filter-field__label">账号归类</span>
        <select v-model="userFilters.accountType" aria-label="账号归类">
          <option value="">全部账号</option>
          <option value="member">普通账号</option>
          <option value="persona">运营/测试账号</option>
        </select>
      </label>
    </div>

    <div class="user-management-layout">
      <aside class="user-list-pane" aria-label="用户列表">
        <header class="pane-heading">
          <div>
            <h2>用户列表</h2>
            <p>最多显示 50 条匹配记录</p>
          </div>
          <TeamOutlined aria-hidden="true" />
        </header>

        <div v-if="usersQuery.isLoading.value" class="user-list-skeleton" role="status">
          <span class="sr-only">用户列表加载中…</span>
          <i v-for="index in 7" :key="index" />
        </div>
        <div v-else-if="usersQuery.isError.value" class="panel-state panel-state--error" role="alert">
          <strong>用户列表加载失败</strong>
          <span>请检查网络或管理员权限后重试。</span>
          <UiButton tone="subtle" :disabled="usersQuery.isFetching.value" @click="usersQuery.refetch()">
            {{ usersQuery.isFetching.value ? "重试中…" : "重新加载" }}
          </UiButton>
        </div>
        <div v-else-if="users.length" class="user-list">
          <button
            v-for="user in users"
            :key="user.id"
            type="button"
            :class="{ 'is-active': user.id === selectedUser?.id }"
            :aria-pressed="user.id === selectedUser?.id"
            @click="selectUser(user)"
          >
            <UiAvatar :src="user.avatar_url" :name="user.username" :role="user.role" :level="user.level" size="sm" />
            <span class="user-list__identity">
              <strong>{{ user.username }}</strong>
              <small>{{ user.email }}</small>
            </span>
            <span class="user-list__meta">
              <em>{{ adminRoleLabel(user.role) }} · {{ operatorIdentity(user.is_persona, user.persona_kind)?.label ?? "普通" }}</em>
              <i :class="`is-${accountStatusClass(user.status)}`">{{ adminStatusLabel(user.status) }}</i>
            </span>
          </button>
        </div>
        <div v-else class="panel-state">
          <strong>没有符合条件的用户</strong>
          <span>尝试清空搜索词或切换角色、状态筛选。</span>
        </div>
      </aside>

      <article v-if="selectedUser" class="user-detail-pane">
        <button ref="detailBackButtonElement" type="button" class="user-detail-back" @click="showUserList">
          <ArrowLeftOutlined aria-hidden="true" />
          返回用户列表
        </button>

        <header class="user-detail-header">
          <UiAvatar
            :src="selectedUser.avatar_url"
            :name="selectedUser.username"
            :role="selectedUser.role"
            :level="selectedUser.level"
            size="lg"
          />
          <div class="user-detail-header__identity">
            <div>
              <h2>{{ selectedUser.username }}</h2>
              <span :class="`account-status is-${accountStatusClass(selectedUser.status)}`">
                {{ adminStatusLabel(selectedUser.status) }}
              </span>
              <OperatorIdentityBadge :is-persona="selectedUser.is_persona" :kind="selectedUser.persona_kind" />
            </div>
            <p>{{ selectedUser.email }}</p>
          </div>
          <span class="role-pill"><SafetyCertificateOutlined aria-hidden="true" />{{ adminRoleLabel(selectedUser.role) }}</span>
        </header>

        <dl class="user-facts">
          <div>
            <dt>内容</dt>
            <dd>{{ selectedUser.topic_count }} 主题 / {{ selectedUser.post_count }} 回复</dd>
          </div>
          <div>
            <dt>等级与成长</dt>
            <dd>Lv.{{ selectedUser.level }} · {{ selectedUser.experience_total }} 成长值</dd>
          </div>
          <div>
            <dt>信任等级</dt>
            <dd>TL{{ selectedUser.trust_level }} · {{ selectedUser.trust_level_label }}</dd>
          </div>
          <div>
            <dt>可用积分</dt>
            <dd>{{ selectedUser.points_balance }} 分</dd>
          </div>
          <div>
            <dt>升级进度</dt>
            <dd>{{ selectedUser.level_progress_percent }}% · 还需 {{ selectedUser.experience_to_next_level }}</dd>
          </div>
          <div>
            <dt>最后活跃</dt>
            <dd>{{ selectedUser.last_seen_at ? relativeTime(selectedUser.last_seen_at) : "未记录" }}</dd>
          </div>
          <div>
            <dt>账号归类</dt>
            <dd>{{ selectedUser.is_persona ? "运营/测试账号" : "普通账号" }}</dd>
          </div>
        </dl>

        <section class="user-editor-section" aria-labelledby="account-permissions-title">
          <header class="form-section-heading">
            <div>
              <h3 id="account-permissions-title">账号权限</h3>
              <p>账号归类用于真人访问统计；角色和状态决定访问与管理范围。</p>
            </div>
          </header>
          <div class="editor-fields editor-fields--account">
            <label>
              <span>角色</span>
              <select v-model="userDraft.role">
                <option value="user">用户</option>
                <option value="moderator">版主</option>
                <option value="admin">管理员</option>
              </select>
            </label>
            <label>
              <span>状态</span>
              <select v-model="userDraft.status">
                <option value="pending_verification">待验证</option>
                <option value="active">正常</option>
                <option value="silenced">禁言</option>
                <option value="suspended">停用</option>
                <option value="deleted">已删除</option>
              </select>
            </label>
            <label>
              <span>等级</span>
              <input v-model.number="userDraft.level" type="number" min="0" max="5" step="1" />
            </label>
            <label>
              <span>账号归类</span>
              <select v-model="userDraft.isPersona">
                <option :value="false">普通账号</option>
                <option :value="true">运营/测试账号</option>
              </select>
            </label>
            <label class="editor-field--wide persona-kind-field">
              <span>公开身份</span>
              <select v-model="userDraft.personaKind" :disabled="!userDraft.isPersona">
                <option :value="null">未细分（运营角色）</option>
                <option v-for="identity in OPERATOR_IDENTITIES" :key="identity.kind" :value="identity.kind">
                  {{ identity.label }}
                </option>
              </select>
              <small class="persona-kind-help">
                {{ operatorIdentity(userDraft.isPersona, userDraft.personaKind)?.description ?? "仅运营/测试账号可选择公开身份。" }}
              </small>
            </label>
          </div>
        </section>

        <section class="user-editor-section" aria-labelledby="growth-adjustment-title">
          <header class="form-section-heading">
            <div>
              <h3 id="growth-adjustment-title">积分与成长</h3>
              <p>仅提交本次增减值；余额、成长值和等级均由后端重新计算。</p>
            </div>
          </header>
          <div class="editor-fields editor-fields--growth">
            <label>
              <span>积分增减</span>
              <input v-model.number="userDraft.pointsDelta" type="number" min="-100000" max="100000" />
            </label>
            <label>
              <span>成长值增减</span>
              <input v-model.number="userDraft.experienceDelta" type="number" min="-100000" max="100000" />
            </label>
            <label class="editor-field--wide">
              <span>调整备注</span>
              <input
                v-model="userDraft.adjustmentReason"
                type="text"
                maxlength="500"
                placeholder="记录人工调整原因（可选）"
              />
            </label>
          </div>
          <div class="user-detail-actions">
            <p v-if="updateUserMutation.isSuccess.value" class="mutation-message is-success" role="status">
              <CheckCircleOutlined aria-hidden="true" /> 用户信息已保存，最新余额以服务端返回为准。
            </p>
            <p v-else-if="updateUserMutation.isError.value" class="mutation-message is-error" role="alert">
              {{ updateUserMutation.error.value?.message || "保存失败，请稍后重试。" }}
            </p>
            <UiButton :disabled="updateUserMutation.isPending.value" @click="saveUser">
              {{ updateUserMutation.isPending.value ? "保存中…" : "保存用户变更" }}
            </UiButton>
          </div>
        </section>

        <section class="user-editor-section user-badge-section" aria-labelledby="badge-management-title">
          <header class="form-section-heading">
            <div>
              <h3 id="badge-management-title">徽章管理</h3>
              <p>{{ selectedUser.badges.length }} 个有效徽章</p>
            </div>
          </header>
          <div v-if="selectedUser.badges.length" class="user-badge-list">
            <span v-for="badge in selectedUser.badges" :key="badge.id" class="user-badge-chip">
              <em>{{ badge.icon }}</em>
              {{ badge.name }}
              <button type="button" :disabled="revokeBadgeMutation.isPending.value" @click="revokeBadge(badge)">
                撤销
              </button>
            </span>
          </div>
          <p v-else class="panel-state is-inline">该用户暂无有效徽章。</p>
          <div class="badge-admin-form">
            <label>
              <span>授予徽章</span>
              <select v-model="badgeDraft.badgeSlug" :disabled="badgesQuery.isLoading.value">
                <option v-for="badge in badgeCatalog" :key="badge.slug" :value="badge.slug">
                  {{ badge.icon }} {{ badge.name }}（TL{{ badge.trust_level_required }}）
                </option>
              </select>
            </label>
            <label>
              <span>授予备注</span>
              <input v-model="badgeDraft.note" maxlength="500" placeholder="授予原因（可选）" />
            </label>
            <label>
              <span>撤销原因</span>
              <input v-model="badgeDraft.revokeReason" maxlength="500" placeholder="撤销时使用（可选）" />
            </label>
            <UiButton
              tone="subtle"
              :disabled="!badgeDraft.badgeSlug || grantBadgeMutation.isPending.value"
              @click="grantBadge"
            >
              {{ grantBadgeMutation.isPending.value ? "授予中…" : "授予徽章" }}
            </UiButton>
          </div>
          <p v-if="badgesQuery.isError.value" class="mutation-message is-error" role="alert">徽章目录加载失败。</p>
          <p v-else-if="grantBadgeMutation.isError.value" class="mutation-message is-error" role="alert">
            {{ grantBadgeMutation.error.value?.message || "授予徽章失败。" }}
          </p>
          <p v-else-if="revokeBadgeMutation.isError.value" class="mutation-message is-error" role="alert">
            {{ revokeBadgeMutation.error.value?.message || "撤销徽章失败。" }}
          </p>
        </section>
      </article>

      <div v-else class="user-detail-empty">
        <TeamOutlined aria-hidden="true" />
        <strong>选择一位用户查看详情</strong>
        <span>用户的权限、成长数据与徽章将在这里显示。</span>
      </div>
    </div>
  </section>
</template>

<style scoped lang="scss" src="./AdminUserManagementPanel.scss"></style>
