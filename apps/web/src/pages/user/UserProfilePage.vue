<script setup lang="ts">
import { computed, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { useCurrentUser } from "@/features/auth/queries";
import { relationshipSummary } from "@/features/social/model";
import {
  useCreatePrivateMessage,
  useUpdateUserRelationship,
  useUserRelationship,
} from "@/features/social/queries";
import TopicList from "@/features/topics/components/TopicList.vue";
import { useUploadAvatar } from "@/features/uploads/queries";
import { useUserProfile, useUserTopics } from "@/features/users/queries";
import { ApiError, hasAccessToken, resolveApiAssetUrl } from "@/shared/api/client";
import { relativeTime } from "@/shared/lib/format";
import UiAvatar from "@/shared/ui/Avatar.vue";
import UiBadge from "@/shared/ui/Badge.vue";
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";

const route = useRoute();
const router = useRouter();
const username = computed(() => String(route.params.username ?? ""));
const avatarInput = ref<HTMLInputElement | null>(null);
const avatarStatus = ref("");
const socialStatus = ref("");
const messageFormOpen = ref(false);
const messageTitle = ref("");
const messageBody = ref("");
const currentUserQuery = useCurrentUser();
const profileQuery = useUserProfile(username);
const topicsQuery = useUserTopics(username);
const profile = computed(() => profileQuery.data.value ?? null);
const avatarMutation = useUploadAvatar(() => profile.value?.username ?? username.value);
const isOwnProfile = computed(
  () => currentUserQuery.data.value?.username === profile.value?.username,
);
const canUseSocialActions = computed(
  () => Boolean(currentUserQuery.data.value && profile.value && !isOwnProfile.value),
);
const relationshipQuery = useUserRelationship(username, canUseSocialActions);
const relationshipMutation = useUpdateUserRelationship(username);
const createMessageMutation = useCreatePrivateMessage();
const relationship = computed(() => relationshipQuery.data.value ?? null);
const socialSummary = computed(() => relationshipSummary(relationship.value));

const joinedAt = computed(() => {
  const createdAt = profile.value?.created_at;
  return createdAt ? relativeTime(createdAt) : "未知";
});

const profileStats = computed(() => {
  const topicCount = profile.value?.topic_count ?? 0;
  const postCount = profile.value?.post_count ?? 0;

  return [
    { label: "主题", value: topicCount, note: topicCount > 0 ? "已发起讨论" : "等待首帖" },
    { label: "楼层", value: postCount, note: postCount > 0 ? "参与回复" : "还没接楼" },
    { label: "贡献", value: topicCount + postCount, note: "公开内容" },
  ];
});

const profileSummary = computed(() => {
  const topicCount = profile.value?.topic_count ?? 0;
  const postCount = profile.value?.post_count ?? 0;

  if (topicCount + postCount === 0) {
    return "还没有留下公开讨论，但这条平行线已经预留好了第一束信号。";
  }

  if (topicCount >= postCount) {
    return "更擅长把问题开成主题，适合作为讨论的起点。";
  }

  return "更常出现在楼层里补充线索，是讨论中的协作者。";
});

function roleLabel(role: string): string {
  const labels: Record<string, string> = {
    admin: "管理员",
    moderator: "版主",
    user: "成员",
  };

  return labels[role] ?? role;
}

function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    active: "正常",
    silenced: "禁言中",
    suspended: "暂停",
    deleted: "已注销",
  };

  return labels[status] ?? status;
}

function openAvatarPicker() {
  if (avatarMutation.isPending.value) {
    return;
  }

  avatarInput.value?.click();
}

function requireLogin() {
  if (hasAccessToken()) {
    return false;
  }

  void router.push({ name: "auth", query: { redirect: route.fullPath } });
  return true;
}

function toggleRelationship(kind: "follow" | "ignore" | "block", active: boolean) {
  if (!profile.value || isOwnProfile.value || requireLogin()) {
    return;
  }

  socialStatus.value = "";
  relationshipMutation.mutate(
    { kind, active },
    {
      onSuccess: (nextState) => {
        if (kind === "follow") {
          socialStatus.value = nextState.following ? "已关注该成员。" : "已取消关注。";
          return;
        }

        if (kind === "ignore") {
          socialStatus.value = nextState.ignored ? "已忽略该成员。" : "已取消忽略。";
          return;
        }

        socialStatus.value = nextState.blocked ? "已屏蔽该成员。" : "已取消屏蔽。";
      },
      onError: (error) => {
        socialStatus.value = socialErrorMessage(error);
      },
    },
  );
}

function openMessageForm() {
  if (!profile.value || isOwnProfile.value || requireLogin()) {
    return;
  }

  messageTitle.value = `和 ${profile.value.username} 的私信`;
  messageFormOpen.value = true;
}

async function sendPrivateMessage() {
  if (!profile.value || !messageBody.value.trim()) {
    socialStatus.value = "请先写下私信内容。";
    return;
  }

  try {
    const created = await createMessageMutation.mutateAsync({
      participant_usernames: [profile.value.username],
      title: messageTitle.value.trim() || `和 ${profile.value.username} 的私信`,
      raw_md: messageBody.value.trim(),
    });
    socialStatus.value = "私信已创建。";
    messageFormOpen.value = false;
    messageBody.value = "";
    void router.push({
      name: "topic-detail",
      params: { id: created.topic.id, slug: created.topic.slug },
    });
  } catch (error) {
    socialStatus.value = socialErrorMessage(error);
  }
}

async function handleAvatarChange(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = "";
  if (!file) {
    return;
  }

  avatarStatus.value = "";
  try {
    await avatarMutation.mutateAsync(file);
    await profileQuery.refetch();
    avatarStatus.value = "头像已更新。";
  } catch (error) {
    avatarStatus.value = avatarErrorMessage(error);
  }
}

function avatarErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === "avatar_must_be_image") {
      return "头像必须是 PNG、JPG、GIF 或 WebP 图片。";
    }
    if (error.code === "upload_too_large") {
      return "头像文件超过大小限制。";
    }
  }

  return "头像上传失败，请确认已登录且文件类型安全。";
}

function socialErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === "relationship_blocked") {
      return "屏蔽边界内无法关注对方。";
    }

    if (error.code === "private_message_blocked") {
      return "屏蔽边界内无法互发私信。";
    }
  }

  return "操作失败，请稍后重试。";
}
</script>

<template>
  <div class="user-profile-page">
    <UiCard class="profile-hero">
      <span class="profile-hero__glow profile-hero__glow--cyan" aria-hidden="true"></span>
      <span class="profile-hero__glow profile-hero__glow--lime" aria-hidden="true"></span>
      <div class="profile-lines" aria-hidden="true">
        <span></span>
        <span></span>
        <span></span>
      </div>

      <div v-if="profileQuery.isLoading.value" class="profile-state">正在加载用户资料…</div>
      <div v-else-if="profileQuery.isError.value" class="profile-state profile-state--error" role="alert">
        用户资料暂时不可用。请稍后重试，或确认用户是否存在。
      </div>
      <template v-else-if="profile">
        <div class="profile-identity">
          <div class="profile-avatar-frame">
            <UiAvatar
              :name="profile.username"
              :src="resolveApiAssetUrl(profile.avatar_url)"
              size="lg"
            />
            <div v-if="isOwnProfile" class="avatar-upload">
              <input
                ref="avatarInput"
                class="avatar-upload__input"
                type="file"
                accept="image/png,image/jpeg,image/gif,image/webp"
                @change="handleAvatarChange"
              />
              <UiButton type="button" tone="ghost" @click="openAvatarPicker">
                {{ avatarMutation.isPending.value ? "上传中…" : "更换头像" }}
              </UiButton>
              <span v-if="avatarStatus" role="status">{{ avatarStatus }}</span>
            </div>
          </div>

          <div class="profile-copy">
            <div class="profile-kicker">
              <UiBadge tone="green">{{ roleLabel(profile.role) }}</UiBadge>
              <UiBadge tone="blue">Lv.{{ profile.level }}</UiBadge>
              <span class="profile-status">
                <span class="profile-status__dot"></span>
                {{ statusLabel(profile.status) }}
              </span>
            </div>
            <h1>{{ profile.username }}</h1>
            <p class="profile-meta">加入 {{ joinedAt }} · 平行线成员档案</p>
            <p class="profile-summary">{{ profileSummary }}</p>
          </div>
        </div>

        <div class="profile-dashboard" aria-label="用户内容统计">
          <dl class="profile-stats">
            <div v-for="stat in profileStats" :key="stat.label">
              <dt>{{ stat.label }}</dt>
              <dd>{{ stat.value }}</dd>
              <span>{{ stat.note }}</span>
            </div>
          </dl>

          <div class="profile-signal-card">
            <span>信号状态</span>
            <strong>{{ profile.topic_count || profile.post_count ? "已接入讨论" : "等待第一条线索" }}</strong>
            <p>公开资料只展示主题与楼层，不暴露邮箱。</p>
          </div>

          <div v-if="!isOwnProfile" class="profile-social-card">
            <span>关系边界</span>
            <strong>{{ socialSummary }}</strong>
            <div class="profile-social-actions">
              <UiButton
                type="button"
                :tone="relationship?.following ? 'success' : 'primary'"
                :disabled="relationshipMutation.isPending.value"
                @click="toggleRelationship('follow', !relationship?.following)"
              >
                {{ relationship?.following ? "已关注" : "关注" }}
              </UiButton>
              <UiButton
                type="button"
                tone="subtle"
                :disabled="relationshipMutation.isPending.value"
                @click="toggleRelationship('ignore', !relationship?.ignored)"
              >
                {{ relationship?.ignored ? "取消忽略" : "忽略" }}
              </UiButton>
              <UiButton
                type="button"
                tone="subtle"
                :disabled="relationshipMutation.isPending.value"
                @click="toggleRelationship('block', !relationship?.blocked)"
              >
                {{ relationship?.blocked ? "取消屏蔽" : "屏蔽" }}
              </UiButton>
              <UiButton type="button" tone="ghost" @click="openMessageForm">私信</UiButton>
            </div>
            <p v-if="socialStatus" class="profile-social-status" role="status">{{ socialStatus }}</p>
            <div v-if="messageFormOpen" class="profile-message-form">
              <label>
                <span>私信标题</span>
                <input v-model="messageTitle" type="text" maxlength="180" />
              </label>
              <label>
                <span>第一条消息</span>
                <textarea
                  v-model="messageBody"
                  rows="4"
                  placeholder="写一段只对参与者可见的上下文…"
                ></textarea>
              </label>
              <div class="profile-message-actions">
                <UiButton
                  type="button"
                  tone="primary"
                  :disabled="createMessageMutation.isPending.value"
                  @click="sendPrivateMessage"
                >
                  {{ createMessageMutation.isPending.value ? "发送中…" : "创建私信" }}
                </UiButton>
                <UiButton type="button" tone="subtle" @click="messageFormOpen = false">
                  取消
                </UiButton>
              </div>
            </div>
          </div>
        </div>
      </template>
    </UiCard>

    <section class="profile-topics" aria-labelledby="profile-topics-title">
      <header>
        <div>
          <UiBadge tone="blue">用户主题</UiBadge>
          <h2 id="profile-topics-title">{{ username }} 的公开主题</h2>
          <p>只收录仍可见的公开讨论，隐藏或删除内容不会出现在这里。</p>
        </div>
      </header>

      <UiCard v-if="topicsQuery.isLoading.value" class="profile-state">正在加载主题…</UiCard>
      <UiCard v-else-if="topicsQuery.isError.value" class="profile-state profile-state--error" role="alert">
        暂时无法读取该用户的主题列表。请稍后重试。
      </UiCard>
      <UiCard v-else-if="!topicsQuery.data.value?.length" class="profile-empty">
        <span class="profile-empty__mark">∅</span>
        <div>
          <strong>还没有可展示的主题</strong>
          <p>等第一篇帖子发布后，这里会变成一条清晰的个人讨论时间线。</p>
        </div>
        <RouterLink class="profile-empty__link" to="/boards">去看看版块</RouterLink>
      </UiCard>
      <TopicList v-else :topics="topicsQuery.data.value" />
    </section>
  </div>
</template>

<style scoped lang="scss" src="./UserProfilePage.scss"></style>
