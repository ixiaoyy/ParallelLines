<script setup lang="ts">
import { computed, ref } from "vue";

import ComposerDrawer from "@/features/topics/components/ComposerDrawer.vue";
import TopicList from "@/features/topics/components/TopicList.vue";
import {
  boards,
  discoveryTabs,
  homeMetrics,
  sidebarLinks,
  tagCloud,
  topics,
  type DiscoveryTab,
} from "@/pages/home/fixtures";
import { compactNumber } from "@/shared/lib/format";
import UiBadge from "@/shared/ui/Badge.vue";
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";

const activeTab = ref<DiscoveryTab["key"]>("latest");

const activeDescription = computed(
  () => discoveryTabs.find((tab) => tab.key === activeTab.value)?.description ?? "",
);

const visibleTopics = computed(() => {
  const sorted = [...topics];

  if (activeTab.value === "top") {
    return sorted.sort((left, right) => right.likeCount + right.replyCount - (left.likeCount + left.replyCount));
  }

  if (activeTab.value === "hot") {
    return sorted.sort((left, right) => right.hotScore - left.hotScore);
  }

  if (activeTab.value === "votes") {
    return sorted.sort((left, right) => right.likeCount - left.likeCount);
  }

  if (activeTab.value === "categories") {
    return sorted.sort((left, right) => left.boardName.localeCompare(right.boardName));
  }

  return sorted;
});

function setActiveTab(tabKey: DiscoveryTab["key"]) {
  activeTab.value = tabKey;
}
</script>

<template>
  <div id="top" class="meta-home">
    <section class="meta-hero" aria-labelledby="home-title">
      <div class="hero-copy">
        <UiBadge tone="blue">参考 Discourse Meta 的中文社区</UiBadge>
        <h1 id="home-title">中文技术讨论现场。</h1>
        <p>
          借鉴 Discourse Meta 的首页信息架构：清晰的发现导航、紧凑的主题列表、分类色条、
          参与者头像、回复/浏览/活动列，以及面向社区治理的常驻入口。
        </p>

        <div class="hero-actions">
          <UiButton tone="primary">发起主题</UiButton>
          <a class="hero-link" href="#guidelines">阅读社区指南</a>
        </div>
      </div>

      <UiCard class="hero-console">
        <div class="console-toolbar" aria-hidden="true">
          <span></span>
          <span></span>
          <span></span>
        </div>
        <pre><code>GET /api/v1/topics?sort={{ activeTab }}
Accept: application/json

{
  "layout": "topic-list",
  "columns": ["topic", "posters", "replies", "views", "activity"]
}</code></pre>
      </UiCard>
    </section>

    <section class="metric-strip" aria-label="社区实时指标">
      <div v-for="metric in homeMetrics" :key="metric.label" class="metric-item">
        <span>{{ metric.label }}</span>
        <strong>{{ metric.value }}</strong>
        <em>{{ metric.trend }}</em>
      </div>
    </section>

    <div class="discovery-layout">
      <aside id="boards" class="category-column" aria-labelledby="categories-title">
        <div class="section-kicker">版块</div>
        <h2 id="categories-title">分类版块</h2>
        <p class="section-note">像 Discourse Category 一样，每个版块都有色彩、说明与治理边界。</p>

        <div class="category-list">
          <article
            v-for="board in boards"
            :key="board.id"
            class="category-row"
            :style="{ '--category-color': board.color }"
          >
            <span class="category-swatch" aria-hidden="true"></span>
            <div>
              <h3>{{ board.name }}</h3>
              <p>{{ board.description }}</p>
              <span>{{ compactNumber(board.followerCount) }} 人关注</span>
            </div>
            <strong>{{ compactNumber(board.topicCount) }}</strong>
          </article>
        </div>
      </aside>

      <main class="timeline-column" aria-label="主题发现流">
        <div class="discovery-controls">
          <div class="discovery-tabs" role="tablist" aria-label="主题筛选">
            <button
              v-for="tab in discoveryTabs"
              :id="`tab-${tab.key}`"
              :key="tab.key"
              type="button"
              role="tab"
              :aria-selected="activeTab === tab.key"
              :class="{ active: activeTab === tab.key }"
              @click="setActiveTab(tab.key)"
            >
              {{ tab.label }}
            </button>
          </div>

          <div class="control-summary">
            <span>{{ activeDescription }}</span>
            <UiButton tone="subtle">全部版块</UiButton>
          </div>
        </div>

        <TopicList :topics="visibleTopics" />
      </main>

      <aside id="hot" class="meta-sidebar" aria-label="侧边栏">
        <ComposerDrawer />

        <UiCard class="sidebar-card">
          <div class="sidebar-heading">
            <span>推荐入口</span>
            <h3>置顶入口</h3>
          </div>
          <ul class="link-list">
            <li v-for="link in sidebarLinks" :key="link.title">
              <a href="#guidelines">{{ link.title }}</a>
              <span>{{ link.meta }}</span>
            </li>
          </ul>
        </UiCard>

        <UiCard id="votes" class="sidebar-card">
          <div class="sidebar-heading">
            <span>热门标签</span>
            <h3>热门标签</h3>
          </div>
          <div class="tag-cloud">
            <a v-for="tag in tagCloud" :key="tag" href="#">{{ tag }}</a>
          </div>
        </UiCard>

        <UiCard id="guidelines" class="sidebar-card guidelines-card">
          <div class="sidebar-heading">
            <span>社区规范</span>
            <h3>发帖前检查</h3>
          </div>
          <ol>
            <li>标题描述具体问题，不要只写“求助”。</li>
            <li>贴出版本、日志、复现步骤和期望结果。</li>
            <li>代码块使用 Markdown，长日志折叠。</li>
          </ol>
        </UiCard>
      </aside>
    </div>
  </div>
</template>

<style scoped lang="scss" src="./HomePage.scss"></style>
