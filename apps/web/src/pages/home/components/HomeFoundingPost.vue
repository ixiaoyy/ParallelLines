<script setup lang="ts">
import { BookOutlined, PushpinOutlined } from "@ant-design/icons-vue";

import type { TopicCardVM } from "@/entities/topic/model";
import { topicDetailRoute } from "@/shared/router/topicRoutes";

defineProps<{ topics: TopicCardVM[] }>();

function qualityPostHelper(topic: TopicCardVM) {
  if (topic.title.includes("社区规范") || topic.tags.includes("社区规范")) {
    return "理性交流、尊重原创、保护隐私";
  }

  return "写给每一位愿意思考、表达与成长的人";
}
</script>

<template>
  <section class="home-founding-post" aria-labelledby="quality-posts-title">
    <div class="founding-post__head">
      <span class="founding-post__pill"><PushpinOutlined /> 置顶质量帖</span>
      <h2 id="quality-posts-title">先读置顶帖，再开始记录和交流</h2>
      <p>论坛初衷与社区规范会长期置顶，帮助新成员快速理解这里的表达方式和边界。</p>
    </div>

    <div class="founding-post__list">
      <article v-for="topic in topics" :key="topic.id" class="founding-post__item">
        <div class="founding-post__icon" aria-hidden="true">
          <BookOutlined />
        </div>
        <div class="founding-post__copy">
          <div class="founding-post__eyebrow">
            <span><PushpinOutlined /> 必读</span>
            <span>{{ qualityPostHelper(topic) }}</span>
          </div>
          <h3>
            <RouterLink :to="topicDetailRoute(topic)">{{ topic.title }}</RouterLink>
          </h3>
          <p>{{ topic.excerpt }}</p>
          <div class="founding-post__tags" aria-label="主题标签">
            <span v-for="tag in topic.tags.slice(0, 3)" :key="tag">#{{ tag }}</span>
          </div>
        </div>
        <RouterLink class="founding-post__action" :to="topicDetailRoute(topic)">阅读全文</RouterLink>
      </article>
    </div>
  </section>
</template>

<style scoped lang="scss" src="./HomeFoundingPost.scss"></style>
