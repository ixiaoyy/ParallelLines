<script setup lang="ts">
import { uiText } from "@/shared/i18n/locale";
import { computed, ref, watch } from "vue";

import type { PollVM } from "@/entities/topic/model";
import { relativeTime } from "@/shared/lib/format";
import UiBadge from "@/shared/ui/Badge.vue";
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";

const props = withDefaults(
  defineProps<{
    poll: PollVM;
    pending?: boolean;
  }>(),
  { pending: false },
);

const emit = defineEmits<{
  vote: [optionIds: string[]];
}>();

const selectedIds = ref<string[]>([]);

watch(
  () => props.poll.selectedOptionIds,
  (ids) => {
    selectedIds.value = [...ids];
  },
  { immediate: true },
);

const selectedSet = computed(() => new Set(selectedIds.value));
const hasVoted = computed(() => props.poll.selectedOptionIds.length > 0);
const isLocked = computed(() => props.poll.closed || props.pending || hasVoted.value);
const hasChanged = computed(() => sortedIds(selectedIds.value) !== sortedIds(props.poll.selectedOptionIds));
const canSubmit = computed(
  () => !isLocked.value && selectedIds.value.length > 0 && hasChanged.value,
);
const pollMeta = computed(() => {
  const type = uiText(props.poll.multipleChoice ? "可多选" : "单选");
  if (props.poll.closed) {
    return uiText("{type} · 已截止", { type });
  }
  if (hasVoted.value) {
    return uiText("{type} · 已投票", { type });
  }

  return props.poll.closesAt
    ? uiText("{type} · {time}截止", { type, time: relativeTime(props.poll.closesAt) })
    : uiText("{type} · 长期开放", { type });
});

function isSelected(optionId: string) {
  return selectedSet.value.has(optionId);
}

function toggleOption(optionId: string) {
  if (isLocked.value) {
    return;
  }

  if (!props.poll.multipleChoice) {
    selectedIds.value = [optionId];
    return;
  }

  selectedIds.value = isSelected(optionId)
    ? selectedIds.value.filter((id) => id !== optionId)
    : [...selectedIds.value, optionId];
}

function votePercent(voteCount: number) {
  if (props.poll.totalVotes <= 0) {
    return 0;
  }

  return Math.round((voteCount / props.poll.totalVotes) * 100);
}

function submitVote() {
  if (!canSubmit.value) {
    return;
  }

  emit("vote", selectedIds.value);
}

function sortedIds(ids: string[]) {
  return [...ids].sort().join("|");
}
</script>

<template>
  <UiCard class="poll-panel" aria-labelledby="poll-panel-title">
    <div class="poll-panel__header">
      <div>
        <span class="panel-kicker">{{ uiText("社区投票") }}</span>
        <h2 id="poll-panel-title">{{ poll.question }}</h2>
      </div>
      <UiBadge :tone="poll.closed ? 'gray' : 'blue'">{{ pollMeta }}</UiBadge>
    </div>

    <fieldset class="poll-options" :disabled="isLocked">
      <legend>{{ uiText("选择投票选项") }}</legend>
      <label
        v-for="option in poll.options"
        :key="option.id"
        class="poll-option"
        :class="{ selected: isSelected(option.id), locked: isLocked }"
      >
        <input
          :type="poll.multipleChoice ? 'checkbox' : 'radio'"
          name="topic-poll-option"
          :checked="isSelected(option.id)"
          @change="toggleOption(option.id)"
        />
        <span class="poll-option__copy">
          <strong>{{ option.label }}</strong>
          <small>{{ uiText("票数：{count}", { count: option.voteCount }) }} · {{ votePercent(option.voteCount) }}%</small>
        </span>
        <span class="poll-option__bar" aria-hidden="true">
          <i :style="{ width: `${votePercent(option.voteCount)}%` }"></i>
        </span>
      </label>
    </fieldset>

    <div class="poll-panel__footer">
      <span>
        {{ uiText("参与人数：{count}", { count: poll.totalVotes }) }} · {{ hasVoted ? uiText("已投票，无法修改") : uiText("已选 {value0} 项", { value0: selectedIds.length }) }}
      </span>
      <UiButton tone="primary" :disabled="!canSubmit" @click="submitVote">
        {{ pending ? uiText("提交中…") : poll.closed ? uiText("投票已截止") : hasVoted ? uiText("已投票") : uiText("提交投票") }}
      </UiButton>
    </div>
  </UiCard>
</template>

<style scoped lang="scss" src="./PollPanel.scss"></style>
