<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { useBoards } from "@/features/boards/queries";
import { useTags } from "@/features/tags/queries";
import type { TopicSort } from "@/features/topics/model";
import { useTopicFeed } from "@/features/topics/queries";
import { discoveryTabs, type DiscoveryTab } from "@/pages/home/discovery";
import {
  AppstoreOutlined,
  FireOutlined,
  HomeOutlined,
  StarFilled,
} from "@ant-design/icons-vue";

import { compactNumber, relativeTime } from "@/shared/lib/format";
import ParallelCrossingMark from "@/shared/ui/ParallelCrossingMark.vue";

const activeTab = ref<DiscoveryTab["key"]>("latest");
const heroSearch = ref("");
const router = useRouter();
const route = useRoute();

const feedSort = computed<TopicSort>(() =>
  activeTab.value === "hot" ? "hot" : activeTab.value === "top" ? "top" : "latest",
);
const boardsQuery = useBoards();
const topicsQuery = useTopicFeed(feedSort);
const tagsQuery = useTags(30);

const boardSummaries = computed(() => boardsQuery.data.value ?? []);
const feedTopics = computed(() => topicsQuery.data.value ?? []);
const topBoards = computed(() => boardSummaries.value.slice(0, 4));
const railBoards = computed(() => boardSummaries.value.slice(0, 8));
const heroBoards = computed(() => boardSummaries.value.slice(0, 4));
const topTags = computed(() => (tagsQuery.data.value ?? []).slice(0, 10));

const communitySignals = computed(() => [
  {
    label: "本月新讨论",
    value: compactNumber(feedTopics.value.length),
    helper: "来自真实 API",
  },
  {
    label: "等待首答",
    value: compactNumber(feedTopics.value.filter((topic) => topic.replyCount === 0).length),
    helper: "最值得切入",
  },
  {
    label: "精选信号",
    value: compactNumber(
      feedTopics.value.filter((topic) => topic.solved || topic.officialReply || topic.featured || topic.pinned).length,
    ),
    helper: "可直接复用",
  },
]);

const hotTopics = computed(() =>
  [...feedTopics.value].sort((left, right) => right.hotScore - left.hotScore).slice(0, 4),
);

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

watch(
  () => route.hash,
  (hash) => {
    if (hash === "#hot") {
      activeTab.value = "hot";
      return;
    }

    if (hash === "#votes") {
      activeTab.value = "votes";
      return;
    }

    if (hash === "#solved") {
      activeTab.value = "top";
    }
  },
  { immediate: true },
);

function setActiveTab(tabKey: DiscoveryTab["key"]) {
  activeTab.value = tabKey;
}

function submitHeroSearch() {
  const q = heroSearch.value.trim();
  if (!q) {
    return;
  }

  void router.push({ name: "search", query: { q } });
}
</script>

<template>
  <div id="top" class="forum-home">
    <div class="home-grid">
      <aside class="left-rail" aria-label="论坛导航">
        <RouterLink class="rail-action" :to="{ name: 'new-topic' }">新建主题</RouterLink>

        <nav class="rail-section rail-section--primary" aria-label="首页导航">
          <RouterLink class="rail-link rail-link--home rail-link--active" to="/">
            <span class="rail-icon" aria-hidden="true"><HomeOutlined /></span>
            <strong>主页</strong>
            <i aria-hidden="true"></i>
          </RouterLink>
          <RouterLink class="rail-link rail-link--topics" :to="{ name: 'home', hash: '#hot' }">
            <span class="rail-icon" aria-hidden="true"><FireOutlined /></span>
            <strong>话题</strong>
          </RouterLink>
          <RouterLink class="rail-link rail-link--signal" :to="{ name: 'home', hash: '#solved' }">
            <span class="rail-icon" aria-hidden="true"><StarFilled /></span>
            <strong>高信号</strong>
          </RouterLink>
          <RouterLink class="rail-link rail-link--more" :to="{ name: 'board-directory' }">
            <span class="rail-icon" aria-hidden="true"><AppstoreOutlined /></span>
            <strong>更多</strong>
          </RouterLink>
        </nav>

        <section class="rail-section" aria-labelledby="rail-boards-title">
          <h2 id="rail-boards-title">版块</h2>
          <p v-if="boardsQuery.isLoading.value" class="rail-state">正在加载版块…</p>
          <p v-else-if="boardsQuery.isError.value" class="rail-state rail-state--error">版块暂时不可用</p>
          <template v-else>
            <RouterLink
              v-for="board in railBoards"
              :key="board.id"
              class="rail-board"
              :to="{ name: 'board-detail', params: { slug: board.slug } }"
              :style="{ '--board-color': board.color }"
            >
              <span class="rail-board-mark" aria-hidden="true"></span>
              <span class="rail-board-copy">
                <strong>{{ board.name }}</strong>
                <small>{{ board.description }}</small>
              </span>
              <em>{{ compactNumber(board.topicCount) }}</em>
            </RouterLink>
          </template>
        </section>

        <section class="rail-section rail-section--tags" aria-labelledby="rail-tags-title">
          <h2 id="rail-tags-title">标签</h2>
          <p v-if="tagsQuery.isLoading.value" class="rail-state">正在加载标签…</p>
          <p v-else-if="tagsQuery.isError.value" class="rail-state rail-state--error">标签暂时不可用</p>
          <template v-else>
            <RouterLink
              v-for="(tag, tagIndex) in topTags.slice(0, 6)"
              :key="tag.id"
              class="rail-tag"
              :class="`rail-tag--tone-${(tagIndex % 6) + 1}`"
              :to="{ name: 'search', query: { q: tag.name, tag: tag.name } }"
            >
              #{{ tag.name }}
            </RouterLink>
          </template>
        </section>
      </aside>

      <main class="main-column" aria-label="平行线首页内容">
        <section class="hero" aria-labelledby="home-hero-title">
          <div class="hero-grid">
            <div class="hero-copy">
              <p class="hero-eyebrow">技术讨论 · 经验分享 · 项目共创</p>
              <h1 id="home-hero-title" class="hero-title">
                <span class="hero-title__line">让不同方向的思考，</span>
                <span class="hero-title__line">
                  在<em class="hero-brand">平行线</em>上汇合。
                </span>
              </h1>
              <p class="hero-lead">
                轻盈、安静的技术论坛——优先呈现最新讨论、热门话题与清晰分类，帮你快速找到值得参与的内容。
              </p>
              <form class="hero-search" role="search" aria-label="搜索平行线主题" @submit.prevent="submitHeroSearch">
                <span aria-hidden="true">⌕</span>
                <input v-model="heroSearch" type="search" placeholder="搜索主题、标签、成员" />
                <button type="submit" :disabled="!heroSearch.trim()">搜索</button>
              </form>
              <div class="hero-cta">
                <RouterLink class="btn btn-primary" :to="{ name: 'new-topic' }">开始讨论</RouterLink>
                <RouterLink class="btn btn-secondary" :to="{ name: 'board-directory' }">浏览分类</RouterLink>
              </div>
            </div>

            <div class="signal-card" aria-label="社区实时信号">
              <div class="signal-visual" aria-hidden="true">
                <ParallelCrossingMark />
              </div>
              <div class="signal-caption">
                <div v-for="signal in communitySignals" :key="signal.label">
                  <strong>{{ signal.value }}</strong>
                  <span>{{ signal.label }}</span>
                  <small>{{ signal.helper }}</small>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section class="section-head" aria-labelledby="category-title">
          <div>
            <h2 id="category-title">推荐分类</h2>
            <p>用少量、明确的入口降低浏览压力。</p>
          </div>
          <RouterLink class="btn btn-secondary" :to="{ name: 'board-directory' }">查看全部分类</RouterLink>
        </section>

        <section class="category-grid" aria-label="推荐分类">
          <p v-if="boardsQuery.isLoading.value" class="panel-state" role="status">正在加载分类…</p>
          <p v-else-if="boardsQuery.isError.value" class="panel-state panel-state--error" role="alert">分类暂时不可用</p>
          <template v-else>
            <RouterLink
              v-for="board in topBoards"
              :key="board.id"
              class="category"
              :to="{ name: 'board-detail', params: { slug: board.slug } }"
              :style="{ '--board-color': board.color }"
            >
              <h3>{{ board.name }}</h3>
              <p>{{ board.description }}</p>
              <div class="category-meta">
                <span>{{ compactNumber(board.topicCount) }} 个主题</span>
                <span>{{ compactNumber(board.postCount) }} 个帖子</span>
              </div>
            </RouterLink>
          </template>
        </section>

        <section class="section-head section-head--feed" aria-labelledby="feed-title">
          <div>
            <h2 id="feed-title">最新讨论</h2>
            <p>列表保持克制：主题、摘要、标签、回复、浏览、动态。</p>
          </div>
        </section>

        <section class="feed" aria-label="主题列表">
          <div class="tabs">
            <div class="tab-list" role="tablist" aria-label="主题筛选">
              <button
                v-for="tab in discoveryTabs"
                :key="tab.key"
                type="button"
                role="tab"
                :aria-selected="activeTab === tab.key"
                :class="['tab', { active: activeTab === tab.key }]"
                @click="setActiveTab(tab.key)"
              >
                {{ tab.label }}
              </button>
            </div>
            <RouterLink class="filter-link" :to="{ name: 'board-directory' }">筛选分类</RouterLink>
          </div>

          <div class="feed-header" aria-hidden="true">
            <span>主题</span>
            <span>回复</span>
            <span>浏览</span>
            <span>活动</span>
          </div>

          <p v-if="topicsQuery.isLoading.value" class="panel-state" role="status">正在加载主题…</p>
          <p v-else-if="topicsQuery.isError.value" class="panel-state panel-state--error" role="alert">
            暂时无法加载主题，请稍后刷新。
          </p>
          <p v-else-if="!visibleTopics.length" class="panel-state">暂无主题。</p>
          <template v-else>
            <article v-for="topic in visibleTopics" :key="topic.id" class="topic-row">
              <div class="topic-main">
                <div class="avatar-stack" aria-hidden="true">
                  <span>{{ topic.authorName.slice(0, 1).toUpperCase() }}</span>
                  <span>{{ topic.boardName.slice(0, 1) }}</span>
                </div>
                <div class="topic-copy">
                  <div class="topic-title-line">
                    <RouterLink class="topic-title" :to="`/t/${topic.slug}/${topic.id}`">{{ topic.title }}</RouterLink>
                    <span v-if="topic.pinned" class="topic-status">置顶</span>
                    <span v-if="topic.featured" class="topic-status topic-status--signal">精选</span>
                    <span v-if="topic.solved" class="topic-status topic-status--solved">已解决</span>
                  </div>
                  <p>{{ topic.excerpt }}</p>
                  <div class="topic-tags">
                    <RouterLink
                      class="board-chip"
                      :to="{ name: 'board-detail', params: { slug: topic.boardSlug } }"
                      :style="{ '--board-color': topic.boardColor }"
                    >
                      {{ topic.boardName }}
                    </RouterLink>
                    <RouterLink
                      v-for="tag in topic.tags.slice(0, 3)"
                      :key="tag"
                      :to="{ name: 'search', query: { q: tag, tag } }"
                    >
                      #{{ tag }}
                    </RouterLink>
                  </div>
                </div>
              </div>
              <div class="metric">{{ compactNumber(topic.replyCount) }}<span>回复</span></div>
              <div class="metric">{{ compactNumber(topic.viewCount) }}<span>浏览</span></div>
              <div class="activity">{{ relativeTime(topic.lastPostedAt) }}</div>
            </article>
          </template>
        </section>
      </main>

      <aside class="sidebar" aria-label="社区侧栏">
        <section class="sidebar-card">
          <h3>本周热议</h3>
          <p v-if="topicsQuery.isLoading.value" class="sidebar-state">正在加载热议…</p>
          <p v-else-if="topicsQuery.isError.value" class="sidebar-state sidebar-state--error">热议暂时不可用</p>
          <template v-else>
            <div v-for="(topic, index) in hotTopics" :key="topic.id" class="hot-item">
              <span class="rank">{{ index + 1 }}</span>
              <div>
                <RouterLink :to="`/t/${topic.slug}/${topic.id}`">{{ topic.title }}</RouterLink>
                <span>{{ compactNumber(topic.replyCount) }} 回复 · {{ topic.boardName }}</span>
              </div>
            </div>
          </template>
        </section>

        <section class="sidebar-card">
          <h3>社区索引</h3>
          <p v-if="tagsQuery.isLoading.value" class="sidebar-state">正在加载标签…</p>
          <p v-else-if="tagsQuery.isError.value" class="sidebar-state sidebar-state--error">标签暂时不可用</p>
          <div v-else class="tag-cloud">
            <RouterLink
              v-for="tag in topTags"
              :key="tag.id"
              :to="{ name: 'search', query: { q: tag.name, tag: tag.name } }"
            >
              #{{ tag.name }}
            </RouterLink>
          </div>
          <div class="stats">
            <div v-for="signal in communitySignals" :key="signal.label" class="stat">
              <strong>{{ signal.value }}</strong>
              <span>{{ signal.label }}</span>
            </div>
          </div>
        </section>

        <section class="sidebar-card sidebar-card--boards">
          <h3>快速进入</h3>
          <p v-if="boardsQuery.isLoading.value" class="sidebar-state">正在加载版块…</p>
          <p v-else-if="boardsQuery.isError.value" class="sidebar-state sidebar-state--error">版块暂时不可用</p>
          <template v-else>
            <RouterLink
              v-for="board in heroBoards"
              :key="board.id"
              :to="{ name: 'board-detail', params: { slug: board.slug } }"
              :style="{ '--board-color': board.color }"
            >
              <span></span>
              <strong>{{ board.name }}</strong>
              <small>{{ compactNumber(board.topicCount) }} 个主题</small>
            </RouterLink>
          </template>
        </section>
      </aside>
    </div>
  </div>
</template>

<style scoped lang="scss" src="./HomePage.scss"></style>
