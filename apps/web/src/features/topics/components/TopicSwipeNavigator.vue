<script setup lang="ts">
import { uiText } from "@/shared/i18n/locale";
import { LeftOutlined, LoadingOutlined, RightOutlined } from "@ant-design/icons-vue";
import { computed } from "vue";

import type { TopicCardVM } from "@/entities/topic/model";
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
  <UiCard v-if="hasNavigation || loading" class="topic-swipe-navigator" :aria-label="uiText('同版块主题导航')">
    <button
      class="topic-swipe-button topic-swipe-button--previous"
      type="button"
      :disabled="!previousTopic"
      @click="emit('navigate', 'previous')"
    >
      <span class="topic-swipe-button__label">
        <LeftOutlined aria-hidden="true" />
        {{ uiText("上一篇") }}
      </span>
      <strong>{{ previousTopic?.title ?? uiText("已经是最新") }}</strong>
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
      <span class="topic-swipe-button__label">
        {{ uiText("下一篇") }}
        <RightOutlined aria-hidden="true" />
      </span>
      <strong>{{ nextTopic?.title ?? uiText("没有更多主题") }}</strong>
    </button>
  </UiCard>
</template>

<style scoped lang="scss" src="./TopicSwipeNavigator.scss"></style>
