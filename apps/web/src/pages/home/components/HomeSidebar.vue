<script setup lang="ts">
import type { TopicCardVM } from "@/entities/topic/model";
import type { TagItemVM } from "@/features/tags/model";
import { compactNumber } from "@/shared/lib/format";
import { topicDetailRoute } from "@/shared/router/topicRoutes";

defineProps<{
  hotTopics: TopicCardVM[];
  tags: TagItemVM[];
  topicsLoading: boolean;
  topicsError: boolean;
  tagsLoading: boolean;
  tagsError: boolean;
}>();
</script>

<template>
  <aside class="home-sidebar" aria-label="社区侧栏">
    <section class="sidebar-card">
      <h3>本周热议</h3>
      <p v-if="topicsLoading" class="sidebar-state">正在加载热议…</p>
      <p v-else-if="topicsError" class="sidebar-state sidebar-state--error">热议暂时不可用</p>
      <template v-else>
        <div v-for="(topic, index) in hotTopics" :key="topic.id" class="hot-item">
          <span class="rank">{{ index + 1 }}</span>
          <div>
            <RouterLink :to="topicDetailRoute(topic)">{{ topic.title }}</RouterLink>
            <span>{{ compactNumber(topic.replyCount) }} 回复 · {{ topic.boardName }}</span>
          </div>
        </div>
      </template>
    </section>

    <section class="sidebar-card">
      <h3>社区索引</h3>
      <p v-if="tagsLoading" class="sidebar-state">正在加载标签…</p>
      <p v-else-if="tagsError" class="sidebar-state sidebar-state--error">标签暂时不可用</p>
      <div v-else class="tag-cloud">
        <RouterLink
          v-for="tag in tags"
          :key="tag.id"
          :to="{ name: 'search', query: { q: tag.name, tag: tag.name } }"
        >
          #{{ tag.name }}
        </RouterLink>
      </div>
    </section>
  </aside>
</template>

<style scoped lang="scss" src="./HomeSidebar.scss"></style>
