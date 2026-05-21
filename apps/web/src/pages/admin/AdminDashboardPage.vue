<script setup lang="ts">
import { computed } from "vue";

import AdminSettingsPanel from "@/features/admin/components/AdminSettingsPanel.vue";
import AdminSystemPanel from "@/features/admin/components/AdminSystemPanel.vue";
import AdminUserManagementPanel from "@/features/admin/components/AdminUserManagementPanel.vue";
import { isAdmin } from "@/features/auth/permissions";
import { useCurrentUser } from "@/features/auth/queries";
import UiCard from "@/shared/ui/Card.vue";

const currentUserQuery = useCurrentUser();
const canAccessAdmin = computed(() => isAdmin(currentUserQuery.data.value));
</script>

<template>
  <div class="admin-dashboard-page">
    <section class="admin-hero" aria-labelledby="admin-title">
      <div>
        <span class="panel-kicker">Operations cockpit</span>
        <h1 id="admin-title">站点后台中枢</h1>
        <p>把站点设置、用户治理、系统健康、邮件日志与审计线索聚合到一个可运营面板。</p>
      </div>
      <RouterLink class="hero-link" :to="{ name: 'admin-moderation' }">进入审核台</RouterLink>
    </section>

    <UiCard v-if="!currentUserQuery.data.value" class="admin-empty">
      <strong>需要登录后访问后台</strong>
      <span>请使用管理员账号登录。</span>
    </UiCard>

    <UiCard v-else-if="!canAccessAdmin" class="admin-empty">
      <strong>当前账号没有后台权限</strong>
      <span>后台设置和用户管理仅限管理员；版主可继续使用审核台。</span>
    </UiCard>

    <template v-else>
      <AdminSystemPanel />
      <section class="admin-main-grid">
        <AdminSettingsPanel />
        <AdminUserManagementPanel />
      </section>
    </template>
  </div>
</template>

<style scoped lang="scss" src="./AdminDashboardPage.scss"></style>
