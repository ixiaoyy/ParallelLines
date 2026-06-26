<script setup lang="ts">
import { computed } from "vue";

import type { PostItemVM } from "@/entities/post/model";
import type { TopicCardVM } from "@/entities/topic/model";
import { resolveApiAssetUrl } from "@/shared/api/client";
import { compactNumber, relativeTime } from "@/shared/lib/format";
import { tagToneClass } from "@/shared/theme/boardPalette";
import { topicDetailRoute } from "@/shared/router/topicRoutes";
import UiAvatar from "@/shared/ui/Avatar.vue";
import UiCard from "@/shared/ui/Card.vue";

const props = defineProps<{
  topic: TopicCardVM;
  posts: PostItemVM[];
  relatedTopics: TopicCardVM[];
}>();

interface TocHeading {
  id: string;
  text: string;
  level: number;
}

const firstPost = computed(() => props.posts.find((post) => post.floor === 1) ?? props.posts[0] ?? null);
const tocHeadings = computed(() => extractHeadings(firstPost.value));
const fallbackFloors = computed(() => props.posts.slice(0, 9));

function extractHeadings(post: PostItemVM | null): TocHeading[] {
  if (!post?.cookedHtml) {
    return [];
  }

  const headings: TocHeading[] = [];
  const headingPattern = /<h([1-4])(?:\s[^>]*)?>([\s\S]*?)<\/h\1>/gi;
  let match: RegExpExecArray | null;
  let index = 0;

  while ((match = headingPattern.exec(post.cookedHtml)) !== null) {
    const level = Number.parseInt(match[1], 10);
    const text = toPlainText(match[2]);
    if (!text) {
      continue;
    }

    headings.push({
      id: `post-${post.floor}-heading-${index}`,
      text,
      level,
    });
    index += 1;
  }

  return headings.slice(0, 12);
}

function toPlainText(value: string) {
  return value
    .replace(/<[^>]+>/g, "")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&#39;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/\s+/g, " ")
    .trim();
}
</script>

<template>
  <aside class="topic-detail-sidebar" aria-label="主题侧边栏">
    <UiCard class="sidebar-panel progress-panel">
      <span class="panel-kicker">楼层</span>
      <h2>快速跳转</h2>
      <nav v-if="tocHeadings.length" class="toc-nav" aria-label="正文目录">
        <a
          v-for="heading in tocHeadings"
          :key="heading.id"
          :class="`toc-level-${heading.level}`"
          :href="`#${heading.id}`"
        >
          {{ heading.text }}
        </a>
      </nav>
      <nav v-else class="floor-nav" aria-label="楼层跳转">
        <a v-for="post in fallbackFloors" :key="post.id" :href="`#post-${post.floor}`">
          #{{ post.floor }}
          <span>{{ post.authorName }}</span>
        </a>
      </nav>
      <div class="sidebar-jumps">
        <a href="#replies">看回复</a>
        <a href="#topic-end">到结尾</a>
      </div>
    </UiCard>

    <UiCard class="sidebar-panel">
      <span class="panel-kicker">参与者</span>
      <h2>正在讨论</h2>
      <div class="participant-stack">
        <UiAvatar
          v-for="poster in topic.posterNames"
          :key="poster"
          :src="poster === topic.authorName ? resolveApiAssetUrl(topic.authorAvatarUrl) : null"
          :name="poster"
          :role="poster === topic.authorName ? topic.authorRole : undefined"
          :level="poster === topic.authorName ? topic.authorLevel : undefined"
          size="sm"
          :title="poster"
        />
      </div>
    </UiCard>

    <UiCard class="sidebar-panel">
      <span class="panel-kicker">标签</span>
      <h2>主题标签</h2>
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
