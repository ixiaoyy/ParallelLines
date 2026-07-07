<script setup lang="ts">
import { ArrowLeftOutlined } from "@ant-design/icons-vue";

import AdminAnalyticsPanel from "@/features/analytics/components/AdminAnalyticsPanel.vue";
</script>

<template>
  <div class="admin-tool-page">
    <section class="admin-tool-hero" aria-labelledby="admin-analytics-title">
      <div>
        <RouterLink class="admin-tool-back" :to="{ name: 'admin-dashboard' }">
          <ArrowLeftOutlined />
          返回后台
        </RouterLink>
        <h1 id="admin-analytics-title">访问统计</h1>
      </div>
    </section>

    <AdminAnalyticsPanel />
  </div>
</template>

<style scoped lang="scss" src="./AdminToolPage.scss"></style>
