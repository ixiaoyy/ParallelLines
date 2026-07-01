<script setup lang="ts">
import { BarChartOutlined, SafetyCertificateOutlined } from "@ant-design/icons-vue";
import { computed } from "vue";

import AdminFrontierNewsPanel from "@/features/admin/components/AdminFrontierNewsPanel.vue";
import AdminIntegrationsPanel from "@/features/admin/components/AdminIntegrationsPanel.vue";
import AdminExternalIntegrationsPanel from "@/features/external-integrations/components/AdminExternalIntegrationsPanel.vue";
import AdminSettingsPanel from "@/features/admin/components/AdminSettingsPanel.vue";
import AdminSystemPanel from "@/features/admin/components/AdminSystemPanel.vue";
import AdminUserManagementPanel from "@/features/admin/components/AdminUserManagementPanel.vue";
import AdminAnalyticsPanel from "@/features/analytics/components/AdminAnalyticsPanel.vue";
import { isAdmin } from "@/features/auth/permissions";
import { useCurrentUser } from "@/features/auth/queries";
import AdminMigrationToolsPanel from "@/features/migrations/components/AdminMigrationToolsPanel.vue";
import AdminPluginsPanel from "@/features/plugins/components/AdminPluginsPanel.vue";
import AdminThemeMarketplacePanel from "@/features/themes/components/AdminThemeMarketplacePanel.vue";
import UiCard from "@/shared/ui/Card.vue";

const currentUserQuery = useCurrentUser();
const canAccessAdmin = computed(() => isAdmin(currentUserQuery.data.value));
</script>

<template>
  <div class="admin-dashboard-page">
    <section class="admin-hero" aria-labelledby="admin-title">
      <h1 id="admin-title">站点后台</h1>
      <div class="admin-hero__actions">
        <a class="hero-link hero-link--subtle" href="#admin-analytics">
          <BarChartOutlined />
          访问看板
        </a>
        <RouterLink class="hero-link" :to="{ name: 'admin-moderation' }">
          <SafetyCertificateOutlined />
          审核台
        </RouterLink>
      </div>
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
      <AdminFrontierNewsPanel />
      <div id="admin-analytics" class="admin-dashboard-page__anchor">
        <AdminAnalyticsPanel />
      </div>
      <section class="admin-main-grid">
        <AdminSettingsPanel />
        <AdminUserManagementPanel />
      </section>
      <AdminIntegrationsPanel />
      <AdminExternalIntegrationsPanel />
      <AdminPluginsPanel />
      <AdminThemeMarketplacePanel />
      <AdminMigrationToolsPanel />
    </template>
  </div>
</template>

<style scoped lang="scss" src="./AdminDashboardPage.scss"></style>
