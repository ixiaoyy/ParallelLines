<script setup lang="ts">
import { computed, ref } from "vue";

import { profileDisplayName, type UserDirectorySort } from "@/features/users/model";
import { useUserDirectory } from "@/features/users/queries";
import { resolveApiAssetUrl } from "@/shared/api/client";
import { relativeTime } from "@/shared/lib/format";
import UiAvatar from "@/shared/ui/Avatar.vue";
import UiBadge from "@/shared/ui/Badge.vue";
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";

const sort = ref<UserDirectorySort>("active");
const directoryQuery = useUserDirectory(sort);
const users = computed(() => directoryQuery.data.value ?? []);

const sortOptions: { label: string; value: UserDirectorySort; description: string }[] = [
  { label: "最近活跃", value: "active", description: "按最近访问与加入时间排序" },
  { label: "等级", value: "level", description: "优先展示等级和成长值更高的成员" },
  { label: "贡献", value: "contribution", description: "按公开主题和回复总数排序" },
];
</script>

<template>
  <div class="user-directory-page">
    <section class="directory-hero">
      <div>
        <UiBadge tone="blue">成员目录</UiBadge>
        <h1>发现社区里的平行线</h1>
        <p>目录只展示公开资料与贡献统计，不包含邮箱、私密资料或隐藏内容。</p>
      </div>
      <div class="directory-sort" aria-label="目录排序">
        <UiButton
          v-for="option in sortOptions"
          :key="option.value"
          type="button"
          :tone="sort === option.value ? 'primary' : 'ghost'"
          :title="option.description"
          @click="sort = option.value"
        >
          {{ option.label }}
        </UiButton>
      </div>
    </section>

    <UiCard v-if="directoryQuery.isLoading.value" class="directory-state">正在加载成员目录…</UiCard>
    <UiCard v-else-if="directoryQuery.isError.value" class="directory-state directory-state--error" role="alert">
      成员目录暂时不可用，请稍后重试。
    </UiCard>
    <section v-else class="directory-grid" aria-label="公开成员列表">
      <RouterLink v-for="user in users" :key="user.id" class="directory-card" :to="{ name: 'user-profile', params: { username: user.username } }">
        <UiAvatar
          :name="user.username"
          :src="resolveApiAssetUrl(user.avatar_url)"
          :role="user.role"
          :level="user.level"
        />
        <div class="directory-card__main">
          <strong>{{ profileDisplayName(user) }}</strong>
          <span>@{{ user.username }} · {{ user.role }}</span>
          <p>主题 {{ user.topic_count }} · 回复 {{ user.post_count }} · {{ user.points_balance }} 可用积分</p>
        </div>
        <div class="directory-card__meta">
          <UiBadge tone="green">Lv.{{ user.level }}</UiBadge>
          <small>TL{{ user.trust_level }} · {{ user.trust_level_label }}</small>
          <small>{{ user.last_seen_at ? relativeTime(user.last_seen_at) : relativeTime(user.created_at) }}</small>
        </div>
      </RouterLink>
    </section>
  </div>
</template>

<style scoped lang="scss" src="./UserDirectoryPage.scss"></style>
