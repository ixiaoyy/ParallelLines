<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
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
import {
  activityTypeLabel,
  profileDisplayName,
  profileVisibilityLabel,
  type UserActivityType,
  type UserProfileUpdateRequest,
} from "@/features/users/model";
import {
  useUpdateMyProfile,
  useUserActivity,
  useUserProfile,
  useUserTopics,
} from "@/features/users/queries";
import { ApiError, hasAccessToken, resolveApiAssetUrl } from "@/shared/api/client";
import { relativeTime } from "@/shared/lib/format";
import { useSeoMeta } from "@/shared/seo/meta";
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
const profileStatus = ref("");
const profileFormOpen = ref(false);
const activityType = ref<UserActivityType>("posts");
const messageFormOpen = ref(false);
const messageTitle = ref("");
const messageBody = ref("");
const currentUserQuery = useCurrentUser();
const profileQuery = useUserProfile(username);
const topicsQuery = useUserTopics(username);
const profile = computed(() => profileQuery.data.value ?? null);
const profileDraft = reactive({
  display_name: "",
  bio: "",
  website_url: "",
  location: "",
  profile_visibility: "public" as "public" | "members" | "private",
  show_activity: true,
  interface_theme: "system" as "system" | "light" | "colorful",
  locale: "zh-CN" as "zh-CN" | "en-US",
});
useSeoMeta(
  computed(() =>
    profile.value
      ? {
          title: `${profileDisplayName(profile.value)} 的公开档案 · 平行线`,
          description: `${profileDisplayName(profile.value)} 在平行线发布了 ${profile.value.topic_count} 个公开主题、${profile.value.post_count} 条公开回复。`,
          canonicalPath: `/u/${profile.value.username}`,
        }
      : null,
  ),
);
const avatarMutation = useUploadAvatar(() => profile.value?.username ?? username.value);
const updateProfileMutation = useUpdateMyProfile(username);
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
const displayName = computed(() => (profile.value ? profileDisplayName(profile.value) : username.value));
const canShowActivity = computed(() => Boolean(profile.value && (profile.value.show_activity || isOwnProfile.value)));
const activityQuery = useUserActivity(username, activityType, canShowActivity);
const activityItems = computed(() => activityQuery.data.value ?? []);

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

const growthProgress = computed(() => profile.value?.level_progress_percent ?? 0);
const profileBadges = computed(() => profile.value?.badges ?? []);
const growthNextText = computed(() => {
  const next = profile.value?.experience_to_next_level ?? 0;
  return next > 0 ? `距离下一级还差 ${next} XP` : "已到达当前最高等级";
});

const profileSummary = computed(() => {
  if (profile.value?.bio) {
    return profile.value.bio;
  }

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

watch(
  profile,
  (value) => {
    if (!value) {
      return;
    }
    profileDraft.display_name = value.display_name ?? "";
    profileDraft.bio = value.bio ?? "";
    profileDraft.website_url = value.website_url ?? "";
    profileDraft.location = value.location ?? "";
    profileDraft.profile_visibility =
      value.profile_visibility === "members" || value.profile_visibility === "private"
        ? value.profile_visibility
        : "public";
    profileDraft.show_activity = value.show_activity;
  },
  { immediate: true },
);

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

async function saveProfile() {
  const payload: UserProfileUpdateRequest = {
    display_name: profileDraft.display_name.trim() || null,
    bio: profileDraft.bio.trim() || null,
    website_url: profileDraft.website_url.trim() || null,
    location: profileDraft.location.trim() || null,
    profile_visibility: profileDraft.profile_visibility,
    show_activity: profileDraft.show_activity,
    interface_theme: profileDraft.interface_theme,
    locale: profileDraft.locale,
  };

  profileStatus.value = "";
  try {
    await updateProfileMutation.mutateAsync(payload);
    await profileQuery.refetch();
    profileStatus.value = "资料设置已保存。";
    profileFormOpen.value = false;
  } catch (error) {
    profileStatus.value = profileErrorMessage(error);
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

function profileErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === "invalid_profile_url") {
      return "个人链接必须以 http:// 或 https:// 开头。";
    }
    if (error.code === "invalid_profile_field") {
      return "资料字段过长，请缩短后再保存。";
    }
  }

  return "资料保存失败，请稍后重试。";
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
              <UiBadge tone="amber">TL{{ profile.trust_level }} · {{ profile.trust_level_label }}</UiBadge>
              <span class="profile-status">
                <span class="profile-status__dot"></span>
                {{ statusLabel(profile.status) }}
              </span>
            </div>
            <h1>{{ displayName }}</h1>
            <p class="profile-meta">
              @{{ profile.username }} · 加入 {{ joinedAt }} · {{ profileVisibilityLabel(profile.profile_visibility) }}
            </p>
            <p class="profile-summary">{{ profileSummary }}</p>
            <div v-if="profile.website_url || profile.location" class="profile-links">
              <a v-if="profile.website_url" :href="profile.website_url" target="_blank" rel="noopener noreferrer">
                {{ profile.website_url }}
              </a>
              <span v-if="profile.location">{{ profile.location }}</span>
            </div>
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

          <div class="profile-growth-card">
            <div>
              <span>成长轨迹</span>
              <strong>Lv.{{ profile.level }} · {{ profile.experience_total }} XP</strong>
              <p>{{ growthNextText }}</p>
            </div>
            <div class="profile-growth-card__points">
              <span>积分余额</span>
              <strong>{{ profile.points_balance }}</strong>
            </div>
            <div class="profile-growth-meter" aria-label="当前等级经验进度">
              <span :style="{ width: `${growthProgress}%` }"></span>
            </div>
          </div>

          <div class="profile-badges-card">
            <span>徽章与信任</span>
            <strong>TL{{ profile.trust_level }} · {{ profile.trust_level_label }}</strong>
            <p>信任等级仅影响发链接、上传和频控边界，不等同于管理员权限。</p>
            <div v-if="profileBadges.length" class="profile-badges-list">
              <span v-for="badge in profileBadges" :key="badge.id" class="profile-badge-chip">
                <em>{{ badge.icon }}</em>
                {{ badge.name }}
              </span>
            </div>
            <p v-else class="profile-badges-empty">暂无公开徽章，完成社区行为后会自动点亮。</p>
          </div>

          <div v-if="isOwnProfile" class="profile-settings-card">
            <div>
              <span>个人设置</span>
              <strong>资料、隐私与界面偏好</strong>
              <p>编辑公开昵称、简介、链接，并决定资料和活动流对谁可见。</p>
            </div>
            <UiButton type="button" tone="primary" @click="profileFormOpen = !profileFormOpen">
              {{ profileFormOpen ? "收起设置" : "编辑资料" }}
            </UiButton>
            <p v-if="profileStatus" class="profile-social-status" role="status">{{ profileStatus }}</p>
            <div v-if="profileFormOpen" class="profile-settings-form">
              <label>
                <span>公开昵称</span>
                <input v-model="profileDraft.display_name" type="text" maxlength="80" />
              </label>
              <label>
                <span>个人简介</span>
                <textarea v-model="profileDraft.bio" rows="4" maxlength="1000"></textarea>
              </label>
              <label>
                <span>个人链接</span>
                <input v-model="profileDraft.website_url" type="url" placeholder="https://example.com" />
              </label>
              <label>
                <span>位置/时区</span>
                <input v-model="profileDraft.location" type="text" maxlength="120" />
              </label>
              <label>
                <span>资料可见性</span>
                <select v-model="profileDraft.profile_visibility">
                  <option value="public">公开</option>
                  <option value="members">仅登录用户</option>
                  <option value="private">仅自己</option>
                </select>
              </label>
              <label class="profile-settings-form__toggle">
                <input v-model="profileDraft.show_activity" type="checkbox" />
                <span>展示公开活动流</span>
              </label>
              <label>
                <span>界面偏好</span>
                <select v-model="profileDraft.interface_theme">
                  <option value="system">跟随系统</option>
                  <option value="light">明亮</option>
                  <option value="colorful">多彩</option>
                </select>
              </label>
              <label>
                <span>语言</span>
                <select v-model="profileDraft.locale">
                  <option value="zh-CN">简体中文</option>
                  <option value="en-US">English</option>
                </select>
              </label>
              <div class="profile-message-actions">
                <UiButton
                  type="button"
                  tone="primary"
                  :disabled="updateProfileMutation.isPending.value"
                  @click="saveProfile"
                >
                  {{ updateProfileMutation.isPending.value ? "保存中…" : "保存资料" }}
                </UiButton>
                <UiButton type="button" tone="subtle" @click="profileFormOpen = false">取消</UiButton>
              </div>
            </div>
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

    <section class="profile-activity" aria-labelledby="profile-activity-title">
      <header>
        <div>
          <UiBadge tone="green">活动页</UiBadge>
          <h2 id="profile-activity-title">{{ displayName }} 的公开活动</h2>
          <p>活动流遵守资料隐私设置；隐藏内容、私信和邮箱不会出现在这里。</p>
        </div>
        <div class="profile-activity-tabs" aria-label="活动类型">
          <UiButton type="button" :tone="activityType === 'posts' ? 'primary' : 'ghost'" @click="activityType = 'posts'">
            回复
          </UiButton>
          <UiButton type="button" :tone="activityType === 'likes' ? 'primary' : 'ghost'" @click="activityType = 'likes'">
            点赞
          </UiButton>
          <UiButton
            type="button"
            :tone="activityType === 'bookmarks' ? 'primary' : 'ghost'"
            @click="activityType = 'bookmarks'"
          >
            收藏
          </UiButton>
        </div>
      </header>

      <UiCard v-if="!canShowActivity" class="profile-state">该成员已关闭公开活动展示。</UiCard>
      <UiCard v-else-if="activityQuery.isLoading.value" class="profile-state">正在加载活动…</UiCard>
      <UiCard v-else-if="activityQuery.isError.value" class="profile-state profile-state--error" role="alert">
        活动暂时不可见，可能被隐私设置隐藏。
      </UiCard>
      <div v-else-if="activityItems.length" class="profile-activity-list">
        <RouterLink
          v-for="item in activityItems"
          :key="item.id"
          class="profile-activity-item"
          :to="{ name: 'topic-detail', params: { id: item.topic_id, slug: item.topic_slug }, hash: item.post_number ? `#post-${item.post_number}` : '' }"
        >
          <UiBadge tone="blue">{{ activityTypeLabel(item.type) }}</UiBadge>
          <div>
            <strong>{{ item.topic_title }}</strong>
            <p>{{ item.excerpt }}</p>
          </div>
          <span>{{ relativeTime(item.created_at) }}</span>
        </RouterLink>
      </div>
      <UiCard v-else class="profile-empty">
        <span class="profile-empty__mark">∅</span>
        <div>
          <strong>暂无该类型公开活动</strong>
          <p>当有公开回复、点赞或收藏后，这里会形成个人活动时间线。</p>
        </div>
      </UiCard>
    </section>
  </div>
</template>

<style scoped lang="scss" src="./UserProfilePage.scss"></style>
