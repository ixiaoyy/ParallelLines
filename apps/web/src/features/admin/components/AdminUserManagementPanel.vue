<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";

import { adminRoleLabel, adminStatusLabel } from "@/features/admin/model";
import type { AdminUserResponse } from "@/features/admin/model";
import { useAdminUsers, useUpdateAdminUser } from "@/features/admin/queries";
import { relativeTime } from "@/shared/lib/format";
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";

const updateUserMutation = useUpdateAdminUser();
const userFilters = reactive({ query: "", role: "", status: "" });
const userParams = computed(() => ({
  limit: 50,
  query: userFilters.query.trim() || undefined,
  role: userFilters.role || undefined,
  status: userFilters.status || undefined,
}));
const usersQuery = useAdminUsers(userParams);
const users = computed(() => usersQuery.data.value ?? []);
const selectedUserId = ref<string | null>(null);
const selectedUser = computed(() =>
  users.value.find((user) => user.id === selectedUserId.value) ?? users.value[0] ?? null,
);
const userDraft = reactive({
  role: "user" as "user" | "moderator" | "admin",
  status: "active" as "active" | "silenced" | "suspended" | "deleted",
  level: 0,
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
  updateUserMutation.mutate({
    userId: selectedUser.value.id,
    payload: { role: userDraft.role, status: userDraft.status, level: Number(userDraft.level) },
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
          <dd>{{ selectedUser.topic_count }} 主题 / {{ selectedUser.post_count }} 帖子</dd>
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
        <input v-model.number="userDraft.level" type="number" min="0" max="100" />
      </label>
      <UiButton :disabled="updateUserMutation.isPending.value" @click="saveUser">保存用户变更</UiButton>
    </UiCard>
  </aside>
</template>

<style scoped lang="scss" src="./AdminUserManagementPanel.scss"></style>
