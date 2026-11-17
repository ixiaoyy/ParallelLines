<script setup lang="ts">
import { uiText } from "@/shared/i18n/locale";
import { computed, ref } from "vue";

import { builtinTrustLabel, profileDisplayName, type UserDirectorySort } from "@/features/users/model";
import OperatorIdentityBadge from "@/features/users/components/OperatorIdentityBadge.vue";
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
  { label: "等级", value: "level", description: "优先展示等级更高的成员" },
  { label: "贡献", value: "contribution", description: "按公开主题和回复总数排序" },
];
</script>

<template>
  <div class="user-directory-page">
    <section class="directory-hero">
      <div>
        <UiBadge tone="blue">{{ uiText("成员目录") }}</UiBadge>
        <h1>{{ uiText("发现社区里的平行线") }}</h1>
        <p>{{ uiText("目录只展示公开资料与贡献统计，不包含邮箱、私密资料或隐藏内容。") }}</p>
      </div>
      <div class="directory-sort" :aria-label="uiText('目录排序')">
        <UiButton
          v-for="option in sortOptions"
          :key="option.value"
          type="button"
          :tone="sort === option.value ? 'primary' : 'ghost'"
          :title="uiText(option.description)"
          @click="sort = option.value"
        >
          {{ uiText(option.label) }}
        </UiButton>
      </div>
    </section>

    <UiCard v-if="directoryQuery.isLoading.value" class="directory-state">{{ uiText("正在加载成员目录…") }}</UiCard>
    <UiCard v-else-if="directoryQuery.isError.value" class="directory-state directory-state--error" role="alert">
      {{ uiText("成员目录暂时不可用，请稍后重试。") }}
    </UiCard>
    <section v-else class="directory-grid" :aria-label="uiText('公开成员列表')">
      <RouterLink v-for="user in users" :key="user.id" class="directory-card" :to="{ name: 'user-profile', params: { id: user.id } }">
        <UiAvatar
          :name="user.username"
          :src="resolveApiAssetUrl(user.avatar_url)"
          :role="user.role"
          :level="user.level"
          loading="lazy"
          decoding="async"
        />
        <div class="directory-card__main">
          <div class="directory-card__identity">
            <strong>{{ profileDisplayName(user) }}</strong>
            <OperatorIdentityBadge :is-persona="user.is_persona" :kind="user.persona_kind" />
          </div>
          <span>@{{ user.username }} · {{ user.role }}</span>
          <p>{{ uiText("主题") }} {{ user.topic_count }} {{ uiText("· 回复") }} {{ user.post_count }} · {{ user.points_balance }} {{ uiText("可用积分") }}</p>
        </div>
        <div class="directory-card__meta">
          <UiBadge tone="green">Lv.{{ user.level }}</UiBadge>
          <small>TL{{ user.trust_level }} · {{ builtinTrustLabel(user.trust_level_label) }}</small>
          <small>{{ user.last_seen_at ? relativeTime(user.last_seen_at) : relativeTime(user.created_at) }}</small>
        </div>
      </RouterLink>
    </section>
  </div>
</template>

<style scoped lang="scss" src="./UserDirectoryPage.scss"></style>
