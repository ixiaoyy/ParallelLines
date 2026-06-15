<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";

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
const selectedUserId = ref<string | null>(null);
const selectedUser = computed(() =>
  users.value.find((user) => user.id === selectedUserId.value) ?? users.value[0] ?? null,
);
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

function selectUser(user: AdminUserResponse) {
  selectedUserId.value = user.id;
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
  <aside class="users-panel">
    <UiCard class="user-search-card">
      <div class="section-head">
        <span class="panel-kicker">Users</span>
        <h2>用户管理</h2>
      </div>
      <div class="user-filters">
        <input v-model="userFilters.query" type="search" placeholder="搜索用户名或邮箱" />
        <select v-model="userFilters.role">
          <option value="">全部角色</option>
          <option value="admin">管理员</option>
          <option value="moderator">版主</option>
          <option value="user">用户</option>
        </select>
        <select v-model="userFilters.status">
          <option value="">全部状态</option>
          <option value="active">正常</option>
          <option value="silenced">禁言</option>
          <option value="suspended">停用</option>
          <option value="deleted">已删除</option>
        </select>
      </div>
      <p v-if="usersQuery.isError.value" class="panel-state panel-state--error" role="alert">
        用户列表加载失败。
      </p>
      <div v-else class="user-list">
        <button
          v-for="user in users"
          :key="user.id"
          type="button"
          :class="{ 'is-active': user.id === selectedUser?.id }"
          @click="selectUser(user)"
        >
          <strong>{{ user.username }}</strong>
          <span>{{ adminRoleLabel(user.role) }} · {{ adminStatusLabel(user.status) }}</span>
        </button>
      </div>
    </UiCard>

    <UiCard v-if="selectedUser" class="user-detail-card">
      <div class="section-head">
        <span class="panel-kicker">Selected user</span>
        <h2>{{ selectedUser.username }}</h2>
      </div>
      <dl class="user-facts">
        <div>
          <dt>邮箱</dt>
          <dd>{{ selectedUser.email }}</dd>
        </div>
        <div>
          <dt>内容</dt>
          <dd>{{ selectedUser.topic_count }} 主题 / {{ selectedUser.post_count }} 回复</dd>
        </div>
        <div>
          <dt>成长</dt>
          <dd>Lv.{{ selectedUser.level }} · {{ selectedUser.experience_total }} 成长值</dd>
        </div>
        <div>
          <dt>信任</dt>
          <dd>TL{{ selectedUser.trust_level }} · {{ selectedUser.trust_level_label }}</dd>
        </div>
        <div>
          <dt>积分</dt>
          <dd>{{ selectedUser.points_balance }} 可用 · 进度 {{ selectedUser.level_progress_percent }}%</dd>
        </div>
        <div>
          <dt>最后活跃</dt>
          <dd>{{ selectedUser.last_seen_at ? relativeTime(selectedUser.last_seen_at) : "未记录" }}</dd>
        </div>
      </dl>
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
      <div class="growth-adjust-grid">
        <label>
          <span>积分调整</span>
          <input v-model.number="userDraft.pointsDelta" type="number" min="-100000" max="100000" />
        </label>
        <label>
          <span>成长值调整</span>
          <input v-model.number="userDraft.experienceDelta" type="number" min="-100000" max="100000" />
        </label>
      </div>
      <label>
        <span>调整备注</span>
        <input v-model="userDraft.adjustmentReason" type="text" maxlength="500" placeholder="人工调整原因（可选）" />
      </label>
      <p class="growth-adjust-note">
        可用积分可用于后续兑换/解锁；成长值只用于等级进度，兑换不会导致等级倒退。
      </p>
      <UiButton :disabled="updateUserMutation.isPending.value" @click="saveUser">保存用户变更</UiButton>

      <section class="user-badge-section" aria-label="徽章管理">
        <div class="section-head">
          <span class="panel-kicker">Badges</span>
          <strong>{{ selectedUser.badges.length }} 个有效徽章</strong>
        </div>
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
  </aside>
</template>

<style scoped lang="scss" src="./AdminUserManagementPanel.scss"></style>
