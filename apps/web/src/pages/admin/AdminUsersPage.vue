<script setup lang="ts">
import { ArrowLeftOutlined } from "@ant-design/icons-vue";

import AdminUserManagementPanel from "@/features/admin/components/AdminUserManagementPanel.vue";
</script>

<template>
  <div class="admin-tool-page">
    <section class="admin-tool-hero" aria-labelledby="admin-users-title">
      <div>
        <RouterLink class="admin-tool-back" :to="{ name: 'admin-dashboard' }">
          <ArrowLeftOutlined />
          返回后台
        </RouterLink>
        <h1 id="admin-users-title">用户管理</h1>
      </div>
    </section>

    <AdminUserManagementPanel />
  </div>
</template>

<style scoped lang="scss" src="./AdminToolPage.scss"></style>
