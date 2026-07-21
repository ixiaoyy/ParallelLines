<script setup lang="ts">
import { ArrowRightOutlined, FileTextOutlined, ToolOutlined } from "@ant-design/icons-vue";
</script>

<template>
  <section class="tools-page" aria-labelledby="tools-page-title">
    <header class="tools-page__header">
      <span><ToolOutlined aria-hidden="true" /> 社区工具箱</span>
      <h1 id="tools-page-title">把重复的小事，做得更省心</h1>
      <p>工具直接服务于社区成员，个人数据默认关联账号并按权限隔离。</p>
    </header>

    <div class="tools-page__grid">
      <RouterLink class="tool-card" :to="{ name: 'daily-report' }">
        <span class="tool-card__icon"><FileTextOutlined aria-hidden="true" /></span>
        <span class="tool-card__content">
          <strong>个人日报助手</strong>
          <small>多轮调整、专属 Prompt、历史表达去重</small>
        </span>
        <em>登录后使用 <ArrowRightOutlined aria-hidden="true" /></em>
      </RouterLink>
    </div>
  </section>
</template>

<style scoped lang="scss" src="./ToolsPage.scss"></style>
