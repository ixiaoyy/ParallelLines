<script setup lang="ts">
import type { PostItemVM } from "@/entities/post/model";
import type { TopicCardVM } from "@/entities/topic/model";
import { compactNumber, relativeTime } from "@/shared/lib/format";
import { tagToneClass } from "@/shared/theme/boardPalette";
import { topicDetailRoute } from "@/shared/router/topicRoutes";
import UiAvatar from "@/shared/ui/Avatar.vue";
import UiCard from "@/shared/ui/Card.vue";

defineProps<{
  topic: TopicCardVM;
  posts: PostItemVM[];
  relatedTopics: TopicCardVM[];
}>();
</script>

<template>
  <aside class="topic-detail-sidebar" aria-label="主题侧边栏">
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
        <RouterLink
          v-for="tag in topic.tags"
          :key="tag"
          class="tone-chip"
          :class="tagToneClass(tag)"
          :to="{ name: 'search', query: { q: tag, tag } }"
        >
          #{{ tag }}
        </RouterLink>
      </div>
    </UiCard>

    <UiCard v-if="relatedTopics.length" class="sidebar-panel">
      <span class="panel-kicker">同版块</span>
      <h2>相关主题</h2>
      <RouterLink
        v-for="related in relatedTopics"
        :key="related.id"
        class="related-topic"
        :to="topicDetailRoute(related)"
      >
        <strong>{{ related.title }}</strong>
        <span>{{ compactNumber(related.replyCount) }} 回复 · {{ relativeTime(related.lastPostedAt) }}</span>
      </RouterLink>
    </UiCard>
  </aside>
</template>

<style scoped lang="scss" src="./TopicDetailSidebar.scss"></style>
