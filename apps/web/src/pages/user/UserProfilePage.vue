<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";

import TopicList from "@/features/topics/components/TopicList.vue";
import { useUserProfile, useUserTopics } from "@/features/users/queries";
import { relativeTime } from "@/shared/lib/format";
import UiAvatar from "@/shared/ui/Avatar.vue";
import UiBadge from "@/shared/ui/Badge.vue";
import UiCard from "@/shared/ui/Card.vue";

const route = useRoute();
const username = computed(() => String(route.params.username ?? ""));
const profileQuery = useUserProfile(username);
const topicsQuery = useUserTopics(username);

const joinedAt = computed(() => {
  const createdAt = profileQuery.data.value?.created_at;
  return createdAt ? relativeTime(createdAt) : "未知";
});
</script>

<template>
  <div class="user-profile-page">
    <UiCard class="profile-hero">
      <div v-if="profileQuery.isLoading.value" class="profile-state">正在加载用户资料…</div>
      <div v-else-if="profileQuery.isError.value" class="profile-state profile-state--error" role="alert">
        用户资料暂时不可用。请稍后重试，或确认用户是否存在。
      </div>
      <template v-else-if="profileQuery.data.value">
        <UiAvatar :name="profileQuery.data.value.username" :src="profileQuery.data.value.avatar_url" size="lg" />
        <div>
          <UiBadge tone="green">{{ profileQuery.data.value.role }}</UiBadge>
          <h1>{{ profileQuery.data.value.username }}</h1>
          <p>状态：{{ profileQuery.data.value.status }} · 加入 {{ joinedAt }}</p>
          <dl class="profile-stats" aria-label="用户内容统计">
            <div>
              <dt>主题</dt>
              <dd>{{ profileQuery.data.value.topic_count }}</dd>
            </div>
            <div>
              <dt>楼层</dt>
              <dd>{{ profileQuery.data.value.post_count }}</dd>
            </div>
          </dl>
        </div>
      </template>
    </UiCard>

    <section class="profile-topics" aria-labelledby="profile-topics-title">
      <header>
        <div>
          <UiBadge tone="blue">用户主题</UiBadge>
          <h2 id="profile-topics-title">{{ username }} 发布的主题</h2>
        </div>
      </header>

      <UiCard v-if="topicsQuery.isLoading.value" class="profile-state">正在加载主题…</UiCard>
      <UiCard v-else-if="topicsQuery.isError.value" class="profile-state profile-state--error" role="alert">
        暂时无法读取该用户的主题列表。请稍后重试。
      </UiCard>
      <UiCard v-else-if="!topicsQuery.data.value?.length" class="profile-state">
        还没有可展示的主题。
      </UiCard>
      <TopicList v-else :topics="topicsQuery.data.value" />
    </section>
  </div>
</template>

<style scoped lang="scss" src="./UserProfilePage.scss"></style>
