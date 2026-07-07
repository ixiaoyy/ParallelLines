<script setup lang="ts">
import {
  BarChartOutlined,
  SafetyCertificateOutlined,
  UserOutlined,
} from "@ant-design/icons-vue";
import { computed } from "vue";

import AdminSystemPanel from "@/features/admin/components/AdminSystemPanel.vue";
import { isAdmin } from "@/features/auth/permissions";
import { useCurrentUser } from "@/features/auth/queries";
import UiCard from "@/shared/ui/Card.vue";

const currentUserQuery = useCurrentUser();
const canAccessAdmin = computed(() => isAdmin(currentUserQuery.data.value));
</script>

<template>
  <div class="admin-dashboard-page">
    <section class="admin-hero" aria-labelledby="admin-title">
      <h1 id="admin-title">站点后台</h1>
    </section>

    <UiCard v-if="!currentUserQuery.data.value" class="admin-empty">
      <strong>需要登录后访问后台</strong>
      <span>请使用管理员账号登录。</span>
    </UiCard>

    <UiCard v-else-if="!canAccessAdmin" class="admin-empty">
      <strong>当前账号没有后台权限</strong>
      <span>后台统计和用户管理仅限管理员；版主可继续使用审核台。</span>
    </UiCard>

    <template v-else>
      <section class="admin-shortcuts" aria-label="后台功能入口">
        <RouterLink class="admin-shortcut" :to="{ name: 'admin-analytics' }">
          <BarChartOutlined />
          <strong>访问统计</strong>
          <span>访问量、访客、来源和入口页</span>
        </RouterLink>
        <RouterLink class="admin-shortcut" :to="{ name: 'admin-users' }">
          <UserOutlined />
          <strong>用户管理</strong>
          <span>用户、角色、状态和成长调整</span>
        </RouterLink>
        <RouterLink class="admin-shortcut" :to="{ name: 'admin-moderation' }">
          <SafetyCertificateOutlined />
          <strong>审核台</strong>
          <span>举报、待审内容和处理记录</span>
        </RouterLink>
      </section>

      <AdminSystemPanel />
    </template>
  </div>
</template>

<style scoped lang="scss" src="./AdminDashboardPage.scss"></style>
