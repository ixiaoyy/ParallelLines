<script setup lang="ts">
import { LeftOutlined, LoadingOutlined, RightOutlined } from "@ant-design/icons-vue";
import { computed } from "vue";

import type { TopicCardVM } from "@/entities/topic/model";
import { compactNumber, relativeTime } from "@/shared/lib/format";
import UiCard from "@/shared/ui/Card.vue";

const props = defineProps<{
  previousTopic: TopicCardVM | null;
  nextTopic: TopicCardVM | null;
  loading: boolean;
}>();

const emit = defineEmits<{
  navigate: [direction: "previous" | "next"];
}>();

const hasNavigation = computed(() => Boolean(props.previousTopic || props.nextTopic));
</script>

<template>
  <UiCard v-if="hasNavigation || loading" class="topic-swipe-navigator" aria-label="同版块主题导航">
    <button
      class="topic-swipe-button"
      type="button"
      :disabled="!previousTopic"
      @click="emit('navigate', 'previous')"
    >
      <LeftOutlined aria-hidden="true" />
      <span>上一篇</span>
      <strong>{{ previousTopic?.title ?? "已经是最新" }}</strong>
      <small v-if="previousTopic">
        {{ compactNumber(previousTopic.replyCount) }} 回复 · {{ relativeTime(previousTopic.lastPostedAt) }}
      </small>
    </button>

    <div class="topic-swipe-divider" aria-hidden="true">
      <LoadingOutlined v-if="loading" />
      <span v-else></span>
    </div>

    <button
      class="topic-swipe-button topic-swipe-button--next"
      type="button"
      :disabled="!nextTopic"
      @click="emit('navigate', 'next')"
    >
      <RightOutlined aria-hidden="true" />
      <span>下一篇</span>
      <strong>{{ nextTopic?.title ?? "没有更多主题" }}</strong>
      <small v-if="nextTopic">
        {{ compactNumber(nextTopic.replyCount) }} 回复 · {{ relativeTime(nextTopic.lastPostedAt) }}
      </small>
    </button>
  </UiCard>
</template>

<style scoped lang="scss" src="./TopicSwipeNavigator.scss"></style>
