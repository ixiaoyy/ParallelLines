<script setup lang="ts">
import { BookOutlined } from "@ant-design/icons-vue";

import type { TopicCardVM } from "@/entities/topic/model";
import { topicDetailRoute } from "@/shared/router/topicRoutes";
import { tagToneClass } from "@/shared/theme/boardPalette";
import UiAvatar from "@/shared/ui/Avatar.vue";

defineProps<{ topics: TopicCardVM[] }>();
</script>

<template>
  <section class="home-founding-post" aria-label="社区准则">
    <div class="founding-post__head">
      <span class="founding-post__pill"><BookOutlined /> 社区准则</span>
    </div>

    <div class="founding-post__list">
      <article v-for="topic in topics" :key="topic.id" class="founding-post__item">
        <div class="founding-post__author" :title="topic.authorName">
          <UiAvatar
            :src="topic.authorAvatarUrl"
            :name="topic.authorName"
            :role="topic.authorRole"
            :level="topic.authorLevel"
            size="lg"
          />
        </div>
        <div class="founding-post__copy">
          <div v-if="topic.featured" class="founding-post__eyebrow">
            <span>精选</span>
          </div>
          <h3>
            <RouterLink :to="topicDetailRoute(topic)">{{ topic.title }}</RouterLink>
          </h3>
          <p>{{ topic.excerpt }}</p>
          <div class="founding-post__tags" aria-label="主题标签">
            <RouterLink
              v-for="tag in topic.tags.slice(0, 3)"
              :key="tag"
              class="founding-post__tag tone-chip"
              :class="tagToneClass(tag)"
              :to="{ name: 'search', query: { q: tag, tag } }"
            >
              #{{ tag }}
            </RouterLink>
          </div>
        </div>
        <RouterLink class="founding-post__action" :to="topicDetailRoute(topic)">阅读全文</RouterLink>
      </article>
    </div>
  </section>
</template>

<style scoped lang="scss" src="./HomeFoundingPost.scss"></style>
