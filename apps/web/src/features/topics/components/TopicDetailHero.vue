<script setup lang="ts">
import { builtinSiteText, currentLocale, uiText } from "@/shared/i18n/locale";
import type { TopicCardVM } from "@/entities/topic/model";
import OperatorIdentityBadge from "@/features/users/components/OperatorIdentityBadge.vue";
import { boardToneClass, tagToneClass } from "@/shared/theme/boardPalette";
import UiBadge from "@/shared/ui/Badge.vue";

defineProps<{
  topic: TopicCardVM;
}>();
</script>

<template>
  <section class="topic-detail-hero" :style="{ '--topic-color': topic.boardColor }" aria-labelledby="topic-title">
    <h1 id="topic-title">{{ topic.title }}</h1>

    <div class="topic-author" :aria-label="uiText('主题作者')">
      <RouterLink :to="{ name: 'user-profile', params: { id: topic.authorId } }">
        {{ topic.authorName }}
      </RouterLink>
      <OperatorIdentityBadge :is-persona="topic.authorIsPersona" :kind="topic.authorPersonaKind" />
    </div>

    <div class="topic-taxonomy" :aria-label="uiText('主题板块与标签')">
      <RouterLink
        class="topic-board-chip"
        :class="boardToneClass(topic.boardSlug)"
        :to="{ name: 'board-detail', params: { slug: topic.boardSlug } }"
      >
        {{ topic.boardName }}
      </RouterLink>
      <UiBadge v-if="topic.pinned" tone="amber">{{ builtinSiteText("topic.pinned", "置顶", currentLocale) }}</UiBadge>
      <UiBadge v-if="topic.featured" tone="green">{{ uiText("精华") }}</UiBadge>
      <UiBadge v-if="topic.solved" tone="green">{{ uiText("已解决") }}</UiBadge>
      <UiBadge v-if="topic.status === 'closed'" tone="gray">{{ uiText("已关闭") }}</UiBadge>
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
  </section>
</template>

<style scoped lang="scss" src="./TopicDetailHero.scss"></style>
