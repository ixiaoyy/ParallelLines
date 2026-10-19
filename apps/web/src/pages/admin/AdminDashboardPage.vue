<script setup lang="ts">
import { computed } from "vue";

import AdminAccessState from "@/features/admin/components/AdminAccessState.vue";
import AdminWorkbenchPanel from "@/features/admin/components/AdminWorkbenchPanel.vue";
import { isAdmin } from "@/features/auth/permissions";
import { useCurrentUser } from "@/features/auth/queries";
import UiButton from "@/shared/ui/Button.vue";

const currentUserQuery = useCurrentUser();
const canAccessAdmin = computed(() => isAdmin(currentUserQuery.data.value));
</script>

<template>
  <AdminAccessState v-if="currentUserQuery.isLoading.value" kind="loading" />
  <AdminAccessState v-else-if="currentUserQuery.isError.value" kind="error">
    <template #actions>
      <UiButton tone="subtle" @click="currentUserQuery.refetch()">重新检查</UiButton>
    </template>
  </AdminAccessState>
  <AdminAccessState
    v-else-if="!currentUserQuery.data.value"
    kind="login"
    :action-to="{ path: '/auth', query: { redirect: '/admin/forum' } }"
    action-label="前往登录"
  />
  <AdminAccessState
    v-else-if="!canAccessAdmin"
    kind="forbidden"
    description="后台数据和用户管理仅限管理员；版主可继续使用审核台。"
    :action-to="{ name: 'admin-moderation' }"
    action-label="前往审核台"
  />
  <AdminWorkbenchPanel v-else />
</template>
