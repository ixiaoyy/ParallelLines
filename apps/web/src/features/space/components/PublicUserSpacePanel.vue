<script setup lang="ts">
import { uiText } from "@/shared/i18n/locale";
import { computed, ref } from "vue";

import UiCard from "@/shared/ui/Card.vue";

import type { SpaceJournalItem } from "../model";
import {
  useDeleteSpaceJournal,
  useLikeSpaceJournal,
  usePublicUserSpace,
  useUpdateSpaceJournal,
} from "../queries";
import SpaceJournalCard from "./SpaceJournalCard.vue";

const props = defineProps<{
  identifier: string;
  displayName: string;
  isOwnProfile: boolean;
}>();

const selectedTag = ref("");
const spaceQuery = usePublicUserSpace(() => props.identifier);
const likeMutation = useLikeSpaceJournal();
const updateJournalMutation = useUpdateSpaceJournal();
const deleteJournalMutation = useDeleteSpaceJournal();

const journals = computed(() => spaceQuery.data.value?.journals ?? []);
const filteredJournals = computed(() => {
  if (!selectedTag.value) return journals.value;
  return journals.value.filter((item) => item.tags?.includes(selectedTag.value));
});

const allTags = computed(() => {
  const counts = new Map<string, number>();
  for (const item of journals.value) {
    for (const tag of item.tags ?? []) {
      counts.set(tag, (counts.get(tag) ?? 0) + 1);
    }
  }
  return Array.from(counts.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 12);
});

function handleLike(entry: SpaceJournalItem) {
  likeMutation.mutate(entry.id);
}

function handleTogglePin(entry: SpaceJournalItem) {
  updateJournalMutation.mutate({
    id: entry.id,
    payload: { is_pinned: !entry.is_pinned },
  });
}

function handleToggleVisibility(entry: SpaceJournalItem) {
  updateJournalMutation.mutate({
    id: entry.id,
    payload: { visibility: entry.visibility === "private" ? "public" : "private" },
  });
}

function handleToggleChecklist(entry: SpaceJournalItem, itemId: string) {
  const nextList = (entry.checklist ?? []).map((item) =>
    item.id === itemId ? { ...item, done: !item.done } : item,
  );
  updateJournalMutation.mutate({
    id: entry.id,
    payload: { checklist: nextList },
  });
}

function handleRemove(entry: SpaceJournalItem) {
  if (typeof window !== "undefined" && !window.confirm(uiText("确定要删除这篇手账吗？"))) {
    return;
  }
  deleteJournalMutation.mutate(entry.id);
}
</script>

<template>
  <section class="profile-space-panel" :aria-label="uiText('个人手账空间')">
    <div class="profile-space-banner">
      <div class="profile-space-banner__copy">
        <span class="profile-space-banner__kicker">{{ uiText('📖 手账与日常空间') }}</span>
        <strong>
          {{ spaceQuery.data.value?.space_title || uiText('{name} 的手账自留地', { name: displayName }) }}
        </strong>
        <p>
          {{
            spaceQuery.data.value?.space_subtitle ||
            (isOwnProfile
              ? uiText('记录日常碎碎念、心情贴纸与私人月度账本，公开手账会展示在你的个人档案页。')
              : uiText('这里展示该成员设为公开的日常手账、心情日签与月度小结卡片。'))
          }}
        </p>
      </div>
      <div class="profile-space-banner__actions">
        <RouterLink v-if="isOwnProfile" class="profile-space-cta" :to="{ name: 'personal-space' }">
          {{ uiText('✍️ 进入手账与记账工作台') }}
        </RouterLink>
        <RouterLink v-else class="profile-space-cta profile-space-cta--soft" :to="{ name: 'personal-space' }">
          {{ uiText('去我的空间') }}
        </RouterLink>
      </div>
    </div>

    <div v-if="allTags.length" class="profile-space-tags" :aria-label="uiText('手账标签筛选')">
      <button
        type="button"
        class="profile-space-tag"
        :class="{ active: !selectedTag }"
        @click="selectedTag = ''"
      >
        {{ uiText('全部 ({count})', { count: journals.length }) }}
      </button>
      <button
        v-for="[tag, count] in allTags"
        :key="tag"
        type="button"
        class="profile-space-tag"
        :class="{ active: selectedTag === tag }"
        @click="selectedTag = selectedTag === tag ? '' : tag"
      >
        #{{ tag }} <em>{{ count }}</em>
      </button>
    </div>

    <UiCard v-if="spaceQuery.isLoading.value" class="profile-space-state">
      {{ uiText('正在加载手账时间线…') }}
    </UiCard>

    <div v-else-if="filteredJournals.length" class="profile-space-timeline">
      <SpaceJournalCard
        v-for="item in filteredJournals"
        :key="item.id"
        :entry="item"
        :editable="isOwnProfile"
        @like="handleLike"
        @toggle-pin="handleTogglePin"
        @toggle-visibility="handleToggleVisibility"
        @toggle-checklist="handleToggleChecklist"
        @remove="handleRemove"
        @select-tag="(tag) => (selectedTag = selectedTag === tag ? '' : tag)"
      />
    </div>

    <UiCard v-else class="profile-space-empty">
      <span class="profile-space-empty__icon" aria-hidden="true">📒</span>
      <div>
        <strong>{{ isOwnProfile ? uiText('还没有写下第一篇手账') : uiText('暂时没有公开的手账记录') }}</strong>
        <p>
          {{
            isOwnProfile
              ? uiText('去个人空间随手记下今天的心情贴纸、待办打卡或一笔日常开销吧。')
              : uiText('当作者将手账设为「公开」后，这里会呈现带心情贴纸的时间轴。')
          }}
        </p>
      </div>
      <RouterLink v-if="isOwnProfile" class="profile-space-cta" :to="{ name: 'personal-space' }">
        {{ uiText('去写第一篇手账') }}
      </RouterLink>
    </UiCard>
  </section>
</template>

<style scoped lang="scss">
.profile-space-panel {
  display: grid;
  gap: 1rem;
}

.profile-space-banner {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 1.15rem 1.25rem;
  border-radius: 1.25rem;
  border: 1px solid color-mix(in srgb, var(--primary) 24%, var(--border));
  background: linear-gradient(135deg, #f0f9ff 0%, #fffdf9 62%, #fef3c7 100%);
  box-shadow: var(--shadow-card);

  &__copy {
    display: grid;
    gap: 0.28rem;
    max-width: 38rem;

    strong {
      font-size: 1.08rem;
      font-weight: 800;
      color: var(--title);
    }

    p {
      margin: 0;
      font-size: 0.86rem;
      color: var(--text);
      line-height: 1.55;
    }
  }

  &__kicker {
    font-size: 0.75rem;
    font-weight: 800;
    color: var(--primary);
    letter-spacing: 0.02em;
  }
}

.profile-space-cta {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 2.55rem;
  padding: 0 1.05rem;
  border-radius: var(--radius-pill);
  border: 1px solid var(--btn-primary-border);
  background: var(--btn-primary-bg);
  color: var(--btn-primary-fg);
  box-shadow: var(--btn-primary-shadow);
  font-size: 0.85rem;
  font-weight: 800;
  text-decoration: none;
  white-space: nowrap;
  transition:
    transform 150ms ease,
    background 150ms ease;

  &:hover {
    transform: translateY(-1px);
    background: var(--btn-primary-bg-hover);
    color: var(--btn-primary-fg-hover);
  }

  &--soft {
    border-color: var(--theme-soft-border);
    background: var(--theme-soft-bg);
    color: var(--theme-soft-fg);
    box-shadow: none;

    &:hover {
      background: var(--theme-soft-bg-hover);
      color: var(--theme-soft-fg-hover);
    }
  }
}

.profile-space-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.42rem;
}

.profile-space-tag {
  display: inline-flex;
  align-items: center;
  gap: 0.28rem;
  padding: 0.3rem 0.72rem;
  border-radius: var(--radius-pill);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text);
  font-size: 0.78rem;
  font-weight: 700;
  cursor: pointer;

  em {
    font-style: normal;
    color: var(--muted);
    font-size: 0.72rem;
  }

  &.active {
    border-color: var(--btn-primary-border);
    background: var(--btn-primary-bg);
    color: var(--btn-primary-fg);

    em {
      color: rgba(255, 255, 255, 0.85);
    }
  }
}

.profile-space-timeline {
  display: grid;
  gap: 0.95rem;
}

.profile-space-state {
  padding: 2rem;
  text-align: center;
  color: var(--muted);
}

.profile-space-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 0.75rem;
  padding: 2.4rem 1.4rem;

  &__icon {
    font-size: 2.2rem;
  }

  strong {
    display: block;
    font-size: 1rem;
    color: var(--title);
    margin-bottom: 0.25rem;
  }

  p {
    margin: 0;
    font-size: 0.86rem;
    color: var(--muted);
    max-width: 26rem;
  }
}
</style>
