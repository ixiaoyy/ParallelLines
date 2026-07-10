<script setup lang="ts">
import { computed, nextTick, reactive, ref, watch } from "vue";

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
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";

const updateUserMutation = useUpdateAdminUser();
const grantBadgeMutation = useGrantAdminUserBadge();
const revokeBadgeMutation = useRevokeAdminUserBadge();
const userFilters = reactive({ query: "", role: "", status: "" });
const userParams = computed(() => ({
  limit: 50,
  query: userFilters.query.trim() || undefined,
  role: userFilters.role || undefined,
  status: userFilters.status || undefined,
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
  status: "active" as "active" | "silenced" | "suspended" | "deleted",
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
      user.status === "silenced" || user.status === "suspended" || user.status === "deleted"
        ? user.status
        : "active";
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
// Key parameters: none. Return value: true at 900px or narrower. Side effect: none.
function isCompactUserLayout(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(max-width: 900px)").matches
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
// Key parameter `user` is the admin user row. Return value: none. Side effect: updates local state, scrolls compact layouts, and moves focus to the detail back button.
function selectUser(user: AdminUserResponse) {
  selectedUserId.value = user.id;
  activePanel.value = "detail";
  if (isCompactUserLayout()) {
    void nextTick(() => {
      usersPanelElement.value?.scrollIntoView({ block: "start" });
      detailBackButtonElement.value?.focus({ preventScroll: true });
    });
  }
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

function saveUser() {
  if (!selectedUser.value) {
    return;
  }
  const payload: AdminUserUpdateRequest = {
    role: userDraft.role,
    status: userDraft.status,
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

function grantBadge() {
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

function revokeBadge(badge: UserBadgeResponse) {
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
        <h1 id="admin-users-title">用户管理</h1>
        <p>搜索用户，维护账号权限、积分成长与徽章。</p>
      </div>
      <span
        v-if="!usersQuery.isLoading.value && !usersQuery.isError.value"
        class="user-result-count"
      >
        当前显示 {{ users.length }} 人
      </span>
    </header>

    <div class="user-management-layout">
      <UiCard class="user-search-card">
        <header class="panel-heading">
          <div>
            <h2>用户列表</h2>
            <p>按用户名、邮箱、角色或状态筛选</p>
          </div>
        </header>

        <div class="user-filters">
          <label class="filter-field filter-field--search">
            <span>搜索用户</span>
            <input
              ref="searchInputElement"
              v-model="userFilters.query"
              type="search"
              placeholder="用户名或邮箱"
            />
          </label>
          <label class="filter-field">
            <span>角色</span>
            <select v-model="userFilters.role">
              <option value="">全部角色</option>
              <option value="admin">管理员</option>
              <option value="moderator">版主</option>
              <option value="user">用户</option>
            </select>
          </label>
          <label class="filter-field">
            <span>状态</span>
            <select v-model="userFilters.status">
              <option value="">全部状态</option>
              <option value="active">正常</option>
              <option value="silenced">禁言</option>
              <option value="suspended">停用</option>
              <option value="deleted">已删除</option>
            </select>
          </label>
        </div>

        <p v-if="usersQuery.isLoading.value" class="panel-state" role="status">用户列表加载中…</p>
        <p v-else-if="usersQuery.isError.value" class="panel-state panel-state--error" role="alert">
          用户列表加载失败。
        </p>
        <div v-else-if="users.length" class="user-list" aria-label="用户列表">
          <button
            v-for="user in users"
            :key="user.id"
            type="button"
            :class="{ 'is-active': user.id === selectedUser?.id }"
            :aria-pressed="user.id === selectedUser?.id"
            @click="selectUser(user)"
          >
            <strong>{{ user.username }}</strong>
            <span>{{ adminRoleLabel(user.role) }} · {{ adminStatusLabel(user.status) }}</span>
          </button>
        </div>
        <p v-else class="panel-state">没有符合筛选条件的用户。</p>
      </UiCard>

      <UiCard v-if="selectedUser" class="user-detail-card">
        <button
          ref="detailBackButtonElement"
          type="button"
          class="user-detail-back"
          @click="showUserList"
        >
          <span aria-hidden="true">←</span>
          返回用户列表
        </button>

        <header class="user-detail-header">
          <div>
            <h2>{{ selectedUser.username }}</h2>
            <p>
              {{ selectedUser.email }} · {{ adminRoleLabel(selectedUser.role) }} ·
              {{ adminStatusLabel(selectedUser.status) }}
            </p>
          </div>
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
            <dd>{{ selectedUser.points_balance }} 分 · 等级进度 {{ selectedUser.level_progress_percent }}%</dd>
          </div>
          <div>
            <dt>最后活跃</dt>
            <dd>{{ selectedUser.last_seen_at ? relativeTime(selectedUser.last_seen_at) : "未记录" }}</dd>
          </div>
        </dl>

        <section class="user-editor-section" aria-labelledby="account-permissions-title">
          <header class="form-section-heading">
            <h3 id="account-permissions-title">账号权限</h3>
            <p>设置用户的角色、账号状态与等级。</p>
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
                <option value="active">正常</option>
                <option value="silenced">禁言</option>
                <option value="suspended">停用</option>
                <option value="deleted">已删除</option>
              </select>
            </label>
            <label>
              <span>等级</span>
              <input v-model.number="userDraft.level" type="number" min="0" max="5" />
            </label>
          </div>
        </section>

        <section class="user-editor-section" aria-labelledby="growth-adjustment-title">
          <header class="form-section-heading">
            <h3 id="growth-adjustment-title">积分与成长</h3>
            <p>输入本次增减值；保存后由后端重新计算余额和等级。</p>
          </header>
          <div class="editor-fields editor-fields--growth">
            <label>
              <span>积分调整</span>
              <input v-model.number="userDraft.pointsDelta" type="number" min="-100000" max="100000" />
            </label>
            <label>
              <span>成长值调整</span>
              <input v-model.number="userDraft.experienceDelta" type="number" min="-100000" max="100000" />
            </label>
            <label class="editor-field--wide">
              <span>调整备注</span>
              <input
                v-model="userDraft.adjustmentReason"
                type="text"
                maxlength="500"
                placeholder="人工调整原因（可选）"
              />
            </label>
          </div>
        </section>

        <div class="user-detail-actions">
          <UiButton :disabled="updateUserMutation.isPending.value" @click="saveUser">保存用户变更</UiButton>
        </div>

        <section class="user-badge-section" aria-labelledby="badge-management-title">
          <header class="form-section-heading">
            <h3 id="badge-management-title">徽章管理</h3>
            <p>{{ selectedUser.badges.length }} 个有效徽章</p>
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
          <p v-else class="growth-adjust-note">暂无有效徽章。</p>
          <div class="badge-admin-form">
            <label>
              <span>授予徽章</span>
              <select v-model="badgeDraft.badgeSlug">
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
          <p v-if="badgesQuery.isError.value" class="panel-state panel-state--error" role="alert">
            徽章目录加载失败。
          </p>
        </section>
      </UiCard>
    </div>
  </section>
</template>

<style scoped lang="scss" src="./AdminUserManagementPanel.scss"></style>
