<script setup lang="ts">
import { computed } from "vue";

import AdminAccessState from "@/features/admin/components/AdminAccessState.vue";
import AdminSystemPanel from "@/features/admin/components/AdminSystemPanel.vue";
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
    :action-to="{ path: '/auth', query: { redirect: '/admin/system' } }"
    action-label="前往登录"
  />
  <AdminAccessState v-else-if="!canAccessAdmin" kind="forbidden" />
  <AdminSystemPanel v-else />
</template>
