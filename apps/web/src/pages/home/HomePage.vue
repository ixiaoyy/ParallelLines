<script setup lang="ts">
import { computed, ref } from "vue";
import { useRouter } from "vue-router";

import { useBoards } from "@/features/boards/queries";
import { useTags } from "@/features/tags/queries";
import TopicList from "@/features/topics/components/TopicList.vue";
import type { TopicSort } from "@/features/topics/model";
import { useTopicFeed } from "@/features/topics/queries";
import { discoveryTabs, type DiscoveryTab } from "@/pages/home/discovery";
import { compactNumber, relativeTime } from "@/shared/lib/format";
import UiBadge from "@/shared/ui/Badge.vue";
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";

const activeTab = ref<DiscoveryTab["key"]>("latest");
const heroSearch = ref("");
const router = useRouter();
const feedSort = computed<TopicSort>(() =>
  activeTab.value === "hot" ? "hot" : activeTab.value === "top" ? "top" : "latest",
);
const boardsQuery = useBoards();
const topicsQuery = useTopicFeed(feedSort);
const tagsQuery = useTags(30);

const activeDescription = computed(
  () => discoveryTabs.find((tab) => tab.key === activeTab.value)?.description ?? "",
);

const boardSummaries = computed(() => boardsQuery.data.value ?? []);
const feedTopics = computed(() => topicsQuery.data.value ?? []);
const tagCloud = computed(() => (tagsQuery.data.value ?? []).map((tag) => tag.name).slice(0, 12));
const heroBoards = computed(() => boardSummaries.value.slice(0, 3));
const hotTopics = computed(() =>
  [...feedTopics.value].sort((left, right) => right.hotScore - left.hotScore).slice(0, 5),
);
const unansweredTopics = computed(() =>
  feedTopics.value.filter((topic) => topic.replyCount === 0).slice(0, 4),
);
const communitySignals = computed(() => [
  {
    label: "公开主题",
    value: compactNumber(feedTopics.value.length),
    helper: "真实 API 主题流",
  },
  {
    label: "等待首答",
    value: compactNumber(feedTopics.value.filter((topic) => topic.replyCount === 0).length),
    helper: "最值得游客切入",
  },
  {
    label: "高信号",
    value: compactNumber(
      feedTopics.value.filter((topic) => topic.solved || topic.officialReply || topic.featured || topic.pinned).length,
    ),
    helper: "可直接复用",
  },
]);

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
  <div id="top" class="meta-home">
    <section class="visitor-hero" aria-labelledby="visitor-hero-title">
      <div class="hero-copy">
        <UiBadge tone="blue">游客入口</UiBadge>
        <h1 id="visitor-hero-title">先找到线索，再加入讨论。</h1>
        <p>
          平行线把问题、复现、答案和后续活动放在同一条线上；你可以先浏览公开主题，确认价值后再登录发帖。
        </p>

        <form class="hero-search" role="search" aria-label="游客搜索" @submit.prevent="submitHeroSearch">
          <input
            v-model="heroSearch"
            type="search"
            placeholder="搜索错误码、模块名、日志关键字，例如 OIDC / CSV / notification_cursor"
          />
          <UiButton type="submit" tone="primary" :disabled="!heroSearch.trim()">搜索线索</UiButton>
        </form>

        <div class="hero-board-strip" aria-label="高频版块">
          <RouterLink
            v-for="board in heroBoards"
            :key="board.id"
            :to="{ name: 'board-detail', params: { slug: board.slug } }"
            :style="{ '--board-color': board.color }"
          >
            <span aria-hidden="true"></span>
            <strong>{{ board.name }}</strong>
            <small>{{ compactNumber(board.topicCount) }} 个主题</small>
          </RouterLink>
        </div>
      </div>

      <div class="hero-signal-grid" aria-label="社区实时信号">
        <div v-for="signal in communitySignals" :key="signal.label">
          <span>{{ signal.label }}</span>
          <strong>{{ signal.value }}</strong>
          <small>{{ signal.helper }}</small>
        </div>
      </div>
    </section>

    <div class="home-workspace">
      <aside class="forum-sidebar" aria-label="社区导航">
        <nav class="primary-menu" aria-label="个人导航">
          <RouterLink class="menu-link active" :to="{ name: 'home', hash: '#top' }">
            <span class="menu-icon menu-icon--stack" aria-hidden="true"></span>
            <span class="menu-text">最新主题</span>
            <i aria-hidden="true"></i>
          </RouterLink>
          <RouterLink class="menu-link" :to="{ name: 'new-topic', hash: '#drafts' }">
            <span class="menu-icon menu-icon--user" aria-hidden="true"></span>
            <span class="menu-text">我的帖子</span>
          </RouterLink>
          <RouterLink class="menu-link" :to="{ name: 'home', hash: '#messages' }">
            <span class="menu-icon menu-icon--inbox" aria-hidden="true"></span>
            <span class="menu-text">我的消息</span>
          </RouterLink>
          <RouterLink class="menu-link" :to="{ name: 'home', hash: '#activity' }">
            <span class="menu-icon menu-icon--calendar" aria-hidden="true"></span>
            <span class="menu-text">近期活动</span>
          </RouterLink>
          <RouterLink class="menu-link menu-link--muted" :to="{ name: 'board-directory' }">
            <span class="menu-icon menu-icon--more" aria-hidden="true"></span>
            <span class="menu-text">更多</span>
          </RouterLink>
        </nav>

        <section id="boards" class="sidebar-section" aria-labelledby="category-nav-title">
          <h2 id="category-nav-title">版块</h2>
          <p v-if="boardsQuery.isLoading.value" class="sidebar-state" role="status">正在加载版块…</p>
          <p v-else-if="boardsQuery.isError.value" class="sidebar-state sidebar-state--error" role="alert">
            版块暂时不可用
          </p>
          <RouterLink
            v-for="board in boardSummaries"
            :key="board.id"
            class="sidebar-link board-link"
            :to="{ name: 'board-detail', params: { slug: board.slug } }"
            :style="{ '--category-color': board.color }"
          >
            <span class="category-square" aria-hidden="true"></span>
            <span class="sidebar-link-copy">
              <strong>{{ board.name }}</strong>
              <small>{{ board.description }}</small>
            </span>
            <em>{{ compactNumber(board.topicCount) }}</em>
          </RouterLink>
          <p v-if="!boardsQuery.isLoading.value && !boardsQuery.isError.value && !boardSummaries.length" class="sidebar-state">
            暂无版块
          </p>
          <RouterLink v-if="!boardsQuery.isError.value" class="sidebar-link sidebar-link--small" to="/boards">
            <span class="menu-icon menu-icon--stack" aria-hidden="true"></span>
            <span class="menu-text">所有版块</span>
          </RouterLink>
        </section>

        <section id="tags" class="sidebar-section" aria-labelledby="tag-nav-title">
          <h2 id="tag-nav-title">标签</h2>
          <p v-if="tagsQuery.isLoading.value" class="sidebar-state" role="status">正在加载标签…</p>
          <p v-else-if="tagsQuery.isError.value" class="sidebar-state sidebar-state--error" role="alert">
            标签暂时不可用
          </p>
          <RouterLink
            v-for="tag in tagCloud.slice(0, 8)"
            :key="tag"
            class="tag-link"
            :to="{ name: 'search', query: { q: tag, tag } }"
          >
            #{{ tag }}
          </RouterLink>
          <p v-if="!tagsQuery.isLoading.value && !tagsQuery.isError.value && !tagCloud.length" class="sidebar-state">
            暂无标签
          </p>
        </section>
      </aside>

      <main class="home-main" aria-label="主题发现流">
        <section class="discourse-page-heading" aria-labelledby="home-title">
          <div>
            <h1 id="home-title">最新主题</h1>
            <p>让讨论沿着线索生长。</p>
          </div>
          <RouterLink class="button-link" :to="{ name: 'new-topic' }">
            <UiButton tone="primary">发起主题</UiButton>
          </RouterLink>
        </section>

        <section class="discourse-toolbar" aria-label="主题筛选">
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
            <span>{{ compactNumber(visibleTopics.length) }} 个主题</span>
            <RouterLink :to="{ name: 'board-directory' }">全部版块</RouterLink>
          </div>
        </section>

        <div v-if="topicsQuery.isError.value" class="home-state home-state--error" role="alert">
          暂时无法加载主题，请稍后刷新。
        </div>
        <TopicList v-else :topics="visibleTopics" />
      </main>

      <aside class="home-insight-rail" aria-label="游客参考">
        <UiCard class="insight-card">
          <span class="panel-kicker">先看这里</span>
          <h2>游客别被首页晃瞎：先挑可行动问题</h2>
          <ol>
            <li>优先看「未回复」：这里最需要补充复现和日志。</li>
            <li>再看「高信号」：已解决/官方回复能直接复用。</li>
            <li>最后再发帖：标题写症状，正文写环境、步骤、日志。</li>
          </ol>
        </UiCard>

        <UiCard class="insight-card">
          <span class="panel-kicker">热度雷达</span>
          <h2>正在升温</h2>
          <ul class="compact-topic-list">
            <li v-for="topic in hotTopics" :key="topic.id">
              <RouterLink :to="`/t/${topic.slug}/${topic.id}`">{{ topic.title }}</RouterLink>
              <small>{{ topic.boardName }} · {{ relativeTime(topic.lastPostedAt) }}</small>
            </li>
          </ul>
        </UiCard>

        <UiCard class="insight-card">
          <span class="panel-kicker">可插手</span>
          <h2>等待首答</h2>
          <ul class="compact-topic-list">
            <li v-for="topic in unansweredTopics" :key="topic.id">
              <RouterLink :to="`/t/${topic.slug}/${topic.id}`">{{ topic.title }}</RouterLink>
              <small>{{ topic.boardName }} · {{ topic.tags.map((tag) => `#${tag}`).join(" ") }}</small>
            </li>
          </ul>
        </UiCard>
      </aside>
    </div>

    <section class="visitor-trust-band" aria-labelledby="visitor-trust-title">
      <div>
        <span class="panel-kicker">投产体验检查</span>
        <h2 id="visitor-trust-title">不是摆拍首页：这里直接暴露真实问题、真实状态和真实入口。</h2>
      </div>
      <ul>
        <li>公开浏览不强迫登录</li>
        <li>标签、版块、搜索互相打通</li>
        <li>发布前有模板和草稿保护</li>
      </ul>
      <RouterLink :to="{ name: 'board-directory' }">从版块开始 →</RouterLink>
    </section>
  </div>
</template>

<style scoped lang="scss" src="./HomePage.scss"></style>
