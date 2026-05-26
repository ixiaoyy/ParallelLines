<script setup lang="ts">
import { BookOutlined, PushpinOutlined } from "@ant-design/icons-vue";

import type { TopicCardVM } from "@/entities/topic/model";
import { topicDetailRoute } from "@/shared/router/topicRoutes";

defineProps<{ topic: TopicCardVM }>();
</script>

<template>
  <aside class="home-founding-post" aria-label="置顶质量帖">
    <div class="founding-post__icon" aria-hidden="true">
      <BookOutlined />
    </div>
    <div class="founding-post__copy">
      <div class="founding-post__eyebrow">
        <span><PushpinOutlined /> 置顶质量帖</span>
        <span>写给每一位愿意思考、表达与成长的人</span>
      </div>
      <h2>
        <RouterLink :to="topicDetailRoute(topic)">{{ topic.title }}</RouterLink>
      </h2>
      <p>{{ topic.excerpt }}</p>
      <div class="founding-post__tags" aria-label="主题标签">
        <span v-for="tag in topic.tags.slice(0, 3)" :key="tag">#{{ tag }}</span>
      </div>
    </div>
    <RouterLink class="founding-post__action" :to="topicDetailRoute(topic)">阅读全文</RouterLink>
  </aside>
</template>

<style scoped lang="scss" src="./HomeFoundingPost.scss"></style>
