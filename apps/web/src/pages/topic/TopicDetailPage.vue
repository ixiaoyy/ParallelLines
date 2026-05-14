<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";

import type { TopicCardVM } from "@/entities/topic/model";
import PostItem from "@/features/posts/components/PostItem.vue";
import ComposerDrawer from "@/features/topics/components/ComposerDrawer.vue";
import {
  getBoardBySlug,
  getPostsByTopicId,
  getRelatedTopics,
  getTopicByRoute,
} from "@/shared/api/mockForum";
import { compactNumber, relativeTime } from "@/shared/lib/format";
import UiAvatar from "@/shared/ui/Avatar.vue";
import UiBadge from "@/shared/ui/Badge.vue";
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";
import UiEmptyState from "@/shared/ui/EmptyState.vue";

const route = useRoute();

const topic = computed(() => getTopicByRoute(route.params.id, route.params.slug));
const board = computed(() => (topic.value ? getBoardBySlug(topic.value.boardSlug) : undefined));
const posts = computed(() => (topic.value ? getPostsByTopicId(topic.value.id) : []));
const relatedTopics = computed<TopicCardVM[]>(() => (topic.value ? getRelatedTopics(topic.value) : []));

const topicStats = computed(() => {
  if (!topic.value) {
    return [];
  }

  return [
    { label: "回复", value: compactNumber(topic.value.replyCount) },
    { label: "浏览", value: compactNumber(topic.value.viewCount) },
    { label: "赞同", value: compactNumber(topic.value.likeCount) },
    { label: "热度", value: String(topic.value.hotScore) },
  ];
});
</script>

<template>
  <div class="topic-detail-page">
    <template v-if="topic">
      <section class="topic-hero" :style="{ '--topic-color': topic.boardColor }" aria-labelledby="topic-title">
        <div class="topic-breadcrumb">
          <RouterLink to="/boards">版块</RouterLink>
          <span>/</span>
          <RouterLink v-if="board" :to="{ name: 'board-detail', params: { slug: board.slug } }">
            {{ board.name }}
          </RouterLink>
        </div>

        <div class="topic-title-block">
          <div class="topic-badges">
            <UiBadge v-if="topic.pinned" tone="amber">置顶</UiBadge>
            <UiBadge v-if="topic.featured" tone="green">精华</UiBadge>
            <UiBadge v-if="topic.solved" tone="green">已解决</UiBadge>
            <UiBadge v-if="topic.status === 'closed'" tone="gray">已关闭</UiBadge>
          </div>
          <h1 id="topic-title">{{ topic.title }}</h1>
          <p>{{ topic.excerpt }}</p>
        </div>

        <div class="topic-author-strip">
          <UiAvatar :name="topic.authorName" size="lg" />
          <div>
            <span>发起人</span>
            <strong>{{ topic.authorName }}</strong>
          </div>
          <time>{{ relativeTime(topic.lastPostedAt) }}有新回复</time>
        </div>

        <dl class="topic-stat-grid" aria-label="主题统计">
          <div v-for="item in topicStats" :key="item.label">
            <dt>{{ item.label }}</dt>
            <dd>{{ item.value }}</dd>
          </div>
        </dl>
      </section>

      <div class="topic-layout">
        <main class="post-stream" aria-label="楼层流">
          <UiCard class="topic-toolbar">
            <div>
              <span class="panel-kicker">楼层流</span>
              <strong>{{ posts.length }} 个可见楼层</strong>
            </div>
            <div class="toolbar-actions">
              <UiButton tone="ghost">只看楼主</UiButton>
              <UiButton tone="subtle">复制链接</UiButton>
            </div>
          </UiCard>

          <div class="post-list">
            <div v-for="post in posts" :id="`post-${post.floor}`" :key="post.id" class="post-anchor">
              <PostItem :post="post" />
            </div>
          </div>

          <ComposerDrawer mode="reply" :topic-title="topic.title" :board-name="topic.boardName" />
        </main>

        <aside class="topic-sidebar" aria-label="主题侧边栏">
          <UiCard class="sidebar-panel progress-panel">
            <span class="panel-kicker">阅读进度</span>
            <h2>楼层导航</h2>
            <nav class="floor-nav" aria-label="楼层跳转">
              <a v-for="post in posts" :key="post.id" :href="`#post-${post.floor}`">
                #{{ post.floor }}
                <span>{{ post.authorName }}</span>
              </a>
            </nav>
          </UiCard>

          <UiCard class="sidebar-panel">
            <span class="panel-kicker">参与者</span>
            <h2>正在讨论</h2>
            <div class="participant-stack">
              <UiAvatar
                v-for="poster in topic.posterNames"
                :key="poster"
                :name="poster"
                size="sm"
                :title="poster"
              />
            </div>
          </UiCard>

          <UiCard class="sidebar-panel">
            <span class="panel-kicker">标签</span>
            <h2>检索线索</h2>
            <div class="tag-list">
              <a v-for="tag in topic.tags" :key="tag" href="#tags">#{{ tag }}</a>
            </div>
          </UiCard>

          <UiCard v-if="relatedTopics.length" class="sidebar-panel">
            <span class="panel-kicker">同版块</span>
            <h2>相关主题</h2>
            <RouterLink
              v-for="related in relatedTopics"
              :key="related.id"
              class="related-topic"
              :to="`/t/${related.slug}/${related.id}`"
            >
              <strong>{{ related.title }}</strong>
              <span>{{ compactNumber(related.replyCount) }} 回复 · {{ relativeTime(related.lastPostedAt) }}</span>
            </RouterLink>
          </UiCard>
        </aside>
      </div>
    </template>

    <UiEmptyState v-else title="没有找到这个主题" description="主题可能已被合并或隐藏，回到首页继续浏览。">
      <RouterLink class="empty-link" to="/">返回首页</RouterLink>
    </UiEmptyState>
  </div>
</template>

<style scoped lang="scss" src="./TopicDetailPage.scss"></style>
