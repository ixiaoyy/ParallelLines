<script setup lang="ts">
import { computed } from "vue";

import AdminAccessState from "@/features/admin/components/AdminAccessState.vue";
import AdminFableSpaceAccessPanel from "@/features/admin/components/AdminFableSpaceAccessPanel.vue";
import { isAdmin } from "@/features/auth/permissions";
import { useCurrentUser } from "@/features/auth/queries";
import UiButton from "@/shared/ui/Button.vue";

const currentUserQuery = useCurrentUser();
// Reuses the forum administrator guard because only operators of ParallelLines may manage product grants.
// Parameters: none. Return value indicates whether the current user can render the panel; side effect: none.
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
    :action-to="{ path: '/auth', query: { redirect: '/admin/fablespace-access' } }"
    action-label="前往登录"
  />
  <AdminAccessState v-else-if="!canAccessAdmin" kind="forbidden" />
  <AdminFableSpaceAccessPanel v-else />
</template>
