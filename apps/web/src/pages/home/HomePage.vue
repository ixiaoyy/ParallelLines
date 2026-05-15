<script setup lang="ts">
import { computed, ref } from "vue";

import { useBoards } from "@/features/boards/queries";
import ComposerDrawer from "@/features/topics/components/ComposerDrawer.vue";
import TopicList from "@/features/topics/components/TopicList.vue";
import type { TopicSort } from "@/features/topics/model";
import { useTopicFeed } from "@/features/topics/queries";
import {
  discoveryTabs,
  homeMetrics,
  sidebarLinks,
  tagCloud,
  type DiscoveryTab,
} from "@/pages/home/fixtures";
import { compactNumber, relativeTime } from "@/shared/lib/format";
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";

const activeTab = ref<DiscoveryTab["key"]>("latest");
const feedSort = computed<TopicSort>(() =>
  activeTab.value === "hot" ? "hot" : activeTab.value === "top" ? "top" : "latest",
);
const boardsQuery = useBoards();
const topicsQuery = useTopicFeed(feedSort);

const activeDescription = computed(
  () => discoveryTabs.find((tab) => tab.key === activeTab.value)?.description ?? "",
);

const boardSummaries = computed(() => boardsQuery.data.value ?? []);
const feedTopics = computed(() => topicsQuery.data.value ?? []);

const visibleTopics = computed(() => {
  const sorted = [...feedTopics.value];

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

const liveTopics = computed(() => feedTopics.value.slice(0, 3));

function setActiveTab(tabKey: DiscoveryTab["key"]) {
  activeTab.value = tabKey;
}
</script>

<template>
  <div id="top" class="meta-home">
    <div class="home-workspace">
      <aside class="forum-sidebar" aria-label="社区导航">
        <nav class="primary-menu" aria-label="个人导航">
          <RouterLink class="menu-link active" :to="{ name: 'home', hash: '#top' }">
            <span class="menu-icon menu-icon--stack" aria-hidden="true"></span>
            话题
            <i aria-hidden="true"></i>
          </RouterLink>
          <RouterLink class="menu-link" :to="{ name: 'new-topic', hash: '#drafts' }">
            <span class="menu-icon menu-icon--user" aria-hidden="true"></span>
            我的帖子
          </RouterLink>
          <RouterLink class="menu-link" :to="{ name: 'home', hash: '#messages' }">
            <span class="menu-icon menu-icon--inbox" aria-hidden="true"></span>
            我的消息
          </RouterLink>
          <RouterLink class="menu-link" :to="{ name: 'home', hash: '#activity' }">
            <span class="menu-icon menu-icon--calendar" aria-hidden="true"></span>
            近期活动
          </RouterLink>
          <RouterLink class="menu-link menu-link--muted" :to="{ name: 'board-directory' }">
            <span class="menu-icon menu-icon--more" aria-hidden="true"></span>
            更多
          </RouterLink>
        </nav>

        <section id="boards" class="taxonomy-section" aria-labelledby="category-nav-title">
          <h2 id="category-nav-title">
            <span aria-hidden="true">⌄</span>
            类别
          </h2>
          <RouterLink
            v-for="board in boardSummaries"
            :key="board.id"
            class="taxonomy-link"
            :to="{ name: 'board-detail', params: { slug: board.slug } }"
            :style="{ '--category-color': board.color }"
          >
            <span class="taxonomy-glyph" aria-hidden="true"></span>
            <span>{{ board.name }}</span>
            <em>{{ compactNumber(board.topicCount) }}</em>
          </RouterLink>
          <RouterLink class="taxonomy-link taxonomy-link--all" to="/boards">
            <span class="taxonomy-glyph taxonomy-glyph--list" aria-hidden="true"></span>
            <span>所有类别</span>
          </RouterLink>
        </section>

        <section id="tags" class="taxonomy-section" aria-labelledby="tag-nav-title">
          <h2 id="tag-nav-title">
            <span aria-hidden="true">⌄</span>
            标签
          </h2>
          <a v-for="tag in tagCloud.slice(0, 7)" :key="tag" class="taxonomy-link tag-nav-link" href="#tags">
            <span class="tag-glyph" aria-hidden="true">#</span>
            <span>{{ tag }}</span>
            <i v-if="['fastapi', '单点登录', '投票'].includes(tag)" aria-hidden="true"></i>
          </a>
          <a class="taxonomy-link taxonomy-link--all" href="#tags">
            <span class="taxonomy-glyph taxonomy-glyph--list" aria-hidden="true"></span>
            <span>所有标签</span>
          </a>
        </section>

        <section class="taxonomy-section" aria-labelledby="channel-nav-title">
          <h2 id="channel-nav-title">
            <span aria-hidden="true">⌄</span>
            频道
          </h2>
          <RouterLink class="channel-link" :to="{ name: 'board-detail', params: { slug: 'community' } }">聊天</RouterLink>
          <RouterLink class="channel-link" :to="{ name: 'board-detail', params: { slug: 'support' } }">快问快答</RouterLink>
        </section>
      </aside>

      <div class="home-main">
        <section class="meta-hero" aria-labelledby="home-title">
          <div class="hero-copy">
            <div class="live-pill" aria-label="社区实时状态">
              <span aria-hidden="true"></span>
              2.4k 人在线 · 刚刚有新回复
            </div>

            <h1 id="home-title">今天的坑，一起填。</h1>
            <p>
              新问题、复盘和提案都进主题流。贴日志，沉淀结论。
            </p>

            <div class="hero-actions">
              <RouterLink class="button-link" :to="{ name: 'new-topic' }">
                <UiButton tone="primary">发起主题</UiButton>
              </RouterLink>
              <a class="hero-link" href="#solved">看已解决</a>
            </div>
          </div>

          <UiCard id="activity" class="hero-live-card" aria-label="正在发生的讨论">
            <header>
              <span>正在发生</span>
              <strong>活跃主题</strong>
            </header>

            <ul class="live-topic-list">
              <li v-for="topic in liveTopics" :key="topic.id">
                <RouterLink :to="`/t/${topic.slug}/${topic.id}`">{{ topic.title }}</RouterLink>
                <p>
                  <span class="live-board" :style="{ '--category-color': topic.boardColor }">
                    <span aria-hidden="true"></span>
                    {{ topic.boardName }}
                  </span>
                  <span>{{ compactNumber(topic.replyCount) }} 回复</span>
                  <span>{{ relativeTime(topic.lastPostedAt) }}</span>
                </p>
              </li>
            </ul>

            <footer>
              <span>值班版主</span>
              <strong>6 人在线</strong>
            </footer>
          </UiCard>
        </section>

        <section id="solved" class="metric-strip" aria-label="社区实时指标">
          <div v-for="metric in homeMetrics" :key="metric.label" class="metric-item">
            <span>{{ metric.label }}</span>
            <strong>{{ metric.value }}</strong>
            <em>{{ metric.trend }}</em>
          </div>
        </section>

        <div class="discovery-layout">
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
                <UiButton tone="subtle">全部类别</UiButton>
              </div>
            </div>

            <TopicList :topics="visibleTopics" />
          </main>

          <aside id="hot" class="meta-sidebar" aria-label="侧边栏">
            <ComposerDrawer />

            <UiCard id="messages" class="sidebar-card">
              <div class="sidebar-heading">
                <span>今日热议</span>
                <h3>还在升温</h3>
              </div>
              <ul class="link-list">
                <li v-for="link in sidebarLinks" :key="link.title">
                  <a href="#hot">{{ link.title }}</a>
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
                <a v-for="tag in tagCloud" :key="tag" href="#tags">{{ tag }}</a>
              </div>
            </UiCard>

            <UiCard id="guidelines" class="sidebar-card guidelines-card">
              <div class="sidebar-heading">
                <span>版务提醒</span>
                <h3>今天的处理</h3>
              </div>
              <ol>
                <li>支持区 12 个重复主题已合并到排障索引。</li>
                <li>3 个已复现缺陷进入本周修复看板。</li>
                <li>插件区的主题投票将在今晚 22:00 截止。</li>
              </ol>
            </UiCard>
          </aside>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss" src="./HomePage.scss"></style>
