<script setup lang="ts">
import { ArrowRightOutlined, ToolOutlined } from "@ant-design/icons-vue";

import SiteNavigation from "@/shared/ui/SiteNavigation.vue";
</script>

<template>
  <div class="tools-shell">
    <header class="tools-site-header">
      <RouterLink class="tools-site-brand" :to="{ name: 'home' }" aria-label="平行线首页">
        <img src="/logo-lines-mark.png" alt="" width="48" height="42" />
        <strong>平行线</strong>
      </RouterLink>
    </header>
    <main class="tools-page" aria-labelledby="tools-page-title">
      <header class="tools-page__header">
        <span><ToolOutlined aria-hidden="true" /> 工具</span>
        <h1 id="tools-page-title">工具</h1>
      </header>
      <article class="tools-tool" aria-labelledby="excel-tool-title">
        <div class="tools-tool__preview" aria-hidden="true">
          <div class="tools-tool__formula"><span>fx</span> =SUMIFS(B2:B3,A2:A3,"张三")</div>
          <div class="tools-tool__sheet">
            <span></span><span>A</span><span>B</span>
            <span>1</span><strong>姓名</strong><strong>金额</strong>
            <span>2</span><span>张三</span><span>100</span>
            <span>3</span><span>张三</span><span>150</span>
            <span>4</span><strong>合计</strong><strong class="tools-tool__answer">250</strong>
          </div>
        </div>
        <div class="tools-tool__content">
          <span class="tools-tool__label">办公工具 · 50 篇完整教程</span>
          <h2 id="excel-tool-title">Excel 公式速查</h2>
          <p>文职常用公式，按步骤照着做。</p>
          <ul class="tools-tool__topics" aria-label="教程内容">
            <li>金额汇总</li><li>人员匹配</li><li>名单核对</li><li>数据清理</li>
          </ul>
          <RouterLink class="tools-tool__launch" :to="{ name: 'tool-excel-formulas' }">
            打开工具 <ArrowRightOutlined aria-hidden="true" />
          </RouterLink>
        </div>
      </article>
    </main>
    <footer class="tools-site-footer"><SiteNavigation /></footer>
  </div>
</template>

<style scoped lang="scss" src="./ToolsPage.scss"></style>
