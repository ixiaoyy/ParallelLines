<script setup lang="ts">
import {
  ArrowLeftOutlined,
  BellOutlined,
  CompassOutlined,
  EditFilled,
  EllipsisOutlined,
  FileTextOutlined,
  HomeOutlined,
  MessageOutlined,
  SearchOutlined,
  TeamOutlined,
  TrophyOutlined,
  UserOutlined,
  UserAddOutlined,
} from "@ant-design/icons-vue";
import { computed, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import type { RouteLocationRaw } from "vue-router";

import { publicSettingString } from "@/features/admin/model";
import { usePublicSiteSettings } from "@/features/admin/queries";
import { isAdmin } from "@/features/auth/permissions";
import {
  useChangePassword,
  useConfirmEmailChange,
  useCurrentUser,
  useRequestEmailChange,
} from "@/features/auth/queries";
import { relationshipSummary, type UserRelationshipListKind } from "@/features/social/model";
import {
  useCreatePrivateMessage,
  useUpdateUserRelationship,
  useUserRelationship,
  useUserRelationshipUsers,
} from "@/features/social/queries";
import TopicList from "@/features/topics/components/TopicList.vue";
import { useAdminTopicDelete } from "@/features/topics/useAdminTopicDelete";
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
  useUserProfileById,
  useUserTopics,
} from "@/features/users/queries";
import { ApiError, hasAccessToken, resolveApiAssetUrl } from "@/shared/api/client";
import { setLocale } from "@/shared/i18n/locale";
import { relativeTime } from "@/shared/lib/format";
import { useSeoMeta } from "@/shared/seo/meta";
import { setInterfaceTheme, type InterfaceTheme } from "@/shared/theme/interfaceTheme";
import UiAvatar from "@/shared/ui/Avatar.vue";
import UiBadge from "@/shared/ui/Badge.vue";
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";
import PasswordField from "@/shared/ui/PasswordField.vue";

type ProfilePanel = "topics" | "activity" | "social" | "profile" | "account";

const ACCOUNT_ROUTE_NAMES = new Set(["account-home", "account-profile", "account-settings"]);
const route = useRoute();
const router = useRouter();
const avatarInput = ref<HTMLInputElement | null>(null);
const avatarStatus = ref("");
const socialStatus = ref("");
const profileStatus = ref("");
const passwordStatus = ref("");
const passwordError = ref("");
const emailStatus = ref("");
const emailError = ref("");
const activeProfilePanel = ref<ProfilePanel>("topics");
const activityType = ref<UserActivityType>("posts");
const socialListKind = ref<UserRelationshipListKind>("following");
const messageFormOpen = ref(false);
const messageTitle = ref("");
const messageBody = ref("");
const currentPassword = ref("");
const newPassword = ref("");
const confirmNewPassword = ref("");
const newEmail = ref("");
const emailPassword = ref("");
const emailToken = ref("");
const currentUserQuery = useCurrentUser();
const siteSettingsQuery = usePublicSiteSettings();
const isAccountRoute = computed(() => ACCOUNT_ROUTE_NAMES.has(String(route.name ?? "")));
const accountUsername = computed(() => (isAccountRoute.value ? currentUserQuery.data.value?.username ?? "" : ""));
const publicUserId = computed(() => (isAccountRoute.value ? "" : String(route.params.id ?? "")));
const accountProfileQuery = useUserProfile(accountUsername);
const publicProfileQuery = useUserProfileById(publicUserId);
const activeProfileQuery = computed(() => (isAccountRoute.value ? accountProfileQuery : publicProfileQuery));
const profile = computed(() => activeProfileQuery.value.data.value ?? null);
const username = computed(() => profile.value?.username ?? accountUsername.value);
const topicsQuery = useUserTopics(username);
const siteTitle = computed(() =>
  publicSettingString(siteSettingsQuery.data.value, "site_title", "平行线"),
);
const isOwnProfile = computed(
  () => Boolean(profile.value && currentUserQuery.data.value?.id === profile.value.id),
);
const canDeleteTopics = computed(() => isAdmin(currentUserQuery.data.value));
const { deletingTopicId, requestDeleteTopic } = useAdminTopicDelete({
  note: "前台个人主题列表管理员删除主题。",
});
const isProfileLoading = computed(
  () =>
    activeProfileQuery.value.isLoading.value ||
    (isAccountRoute.value && (currentUserQuery.isLoading.value || !accountUsername.value)),
);
const isProfileError = computed(() => activeProfileQuery.value.isError.value);
const routePanel = computed<ProfilePanel | null>(() => {
  if (route.name === "account-profile") {
    return "profile";
  }

  if (route.name === "account-settings") {
    return "account";
  }

  if (route.name === "account-home") {
    return "topics";
  }

  return null;
});
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
  computed(() => {
    if (!profile.value) {
      return null;
    }

    const accountCanonical =
      route.name === "account-profile"
        ? "/account/profile"
        : route.name === "account-settings"
          ? "/account/settings"
          : "/account";

    return {
      title: isOwnProfile.value
        ? `${profileDisplayName(profile.value)} 的个人中心 · ${siteTitle.value}`
        : `${profileDisplayName(profile.value)} 的公开档案 · ${siteTitle.value}`,
      description: isOwnProfile.value
        ? "查看自己的讨论、资料、成长记录，并管理账号密码和登录邮箱。"
        : `${profileDisplayName(profile.value)} 在平行线发布了 ${profile.value.topic_count} 个公开主题、${profile.value.post_count} 条公开回复。`,
      canonicalPath: isAccountRoute.value
        ? accountCanonical
        : `/members/${encodeURIComponent(profile.value.id)}`,
      robots: isAccountRoute.value ? "noindex,nofollow" : undefined,
    };
  }),
);
const avatarMutation = useUploadAvatar(() => profile.value?.username ?? username.value);
const updateProfileMutation = useUpdateMyProfile(username);
const changePasswordMutation = useChangePassword();
const requestEmailChangeMutation = useRequestEmailChange();
const confirmEmailChangeMutation = useConfirmEmailChange();
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
const canViewRelationshipLists = computed(() => {
  if (!profile.value) {
    return false;
  }

  if (profile.value.profile_visibility === "public" || profile.value.can_edit) {
    return true;
  }

  return profile.value.profile_visibility === "members" && Boolean(currentUserQuery.data.value);
});
const relationshipUsersQuery = useUserRelationshipUsers(
  username,
  socialListKind,
  computed(() => activeProfilePanel.value === "social" && canViewRelationshipLists.value),
);
const relationshipUsers = computed(() => relationshipUsersQuery.data.value ?? []);

// profilePanels 用途：根据访问者身份组织个人页主内容切换项；无参数，返回可渲染面板列表且无副作用。
const profilePanels = computed<Array<{ key: ProfilePanel; label: string }>>(() => {
  const panels: Array<{ key: ProfilePanel; label: string }> = [
    { key: "topics", label: "主题" },
    { key: "activity", label: "活动" },
  ];

  if (canViewRelationshipLists.value) {
    panels.push({ key: "social", label: "关注" });
  }

  if (isOwnProfile.value) {
    panels.push({ key: "profile", label: "资料" }, { key: "account", label: "账号" });
  }

  return panels;
});

const joinedAt = computed(() => {
  const createdAt = profile.value?.created_at;
  return createdAt ? relativeTime(createdAt) : "未知";
});

const profileStats = computed(() => {
  const topicCount = profile.value?.topic_count ?? 0;
  const postCount = profile.value?.post_count ?? 0;
  const followingCount = profile.value?.following_count ?? 0;
  const followerCount = profile.value?.follower_count ?? 0;

  return [
    { label: "主题", value: topicCount, note: topicCount > 0 ? "已发起讨论" : "等待首帖", icon: FileTextOutlined },
    { label: "回复", value: postCount, note: postCount > 0 ? "参与讨论" : "还没有回复", icon: MessageOutlined },
    { label: "关注", value: followingCount, note: followingCount > 0 ? "正在关注" : "还未关注", icon: UserAddOutlined },
    { label: "粉丝", value: followerCount, note: followerCount > 0 ? "关注者" : "等待关注", icon: TeamOutlined },
  ];
});

const profileBadges = computed(() => profile.value?.badges ?? []);
const profileSummary = computed(() => profile.value?.bio?.trim() ?? "");
// levelProgressPercent 用途：把后端等级进度限制到 0-100，供进度条样式使用；无参数，返回百分比数字且无副作用。
const levelProgressPercent = computed(() => Math.min(100, Math.max(0, profile.value?.level_progress_percent ?? 0)));
// levelProgressStyle 用途：把等级进度写入局部 CSS 变量；无参数，返回样式对象且无副作用。
const levelProgressStyle = computed(() => ({ "--profile-level-progress": `${levelProgressPercent.value}%` }));
// activeBoardSummaries 用途：从用户公开主题列表聚合参与版块；无参数，返回最多三个真实版块摘要且无副作用。
const activeBoardSummaries = computed(() => {
  const boards = new Map<string, { slug: string; name: string; color: string; topicCount: number; replyCount: number }>();

  for (const topic of topicsQuery.data.value ?? []) {
    const existing = boards.get(topic.boardSlug) ?? {
      slug: topic.boardSlug,
      name: topic.boardName,
      color: topic.boardColor,
      topicCount: 0,
      replyCount: 0,
    };
    existing.topicCount += 1;
    existing.replyCount += topic.replyCount;
    boards.set(topic.boardSlug, existing);
  }

  return Array.from(boards.values())
    .sort((left, right) => right.topicCount + right.replyCount - (left.topicCount + left.replyCount))
    .slice(0, 3);
});
const socialPanelTitle = computed(() => (isOwnProfile.value ? "我的关注" : "关注关系"));
const socialFollowingLabel = computed(() => (isOwnProfile.value ? "我关注的" : "TA 关注的"));
const socialFollowersLabel = computed(() => (isOwnProfile.value ? "关注我的" : "关注 TA 的"));
const socialEmptyTitle = computed(() =>
  socialListKind.value === "following" ? "还没有关注任何成员" : "还没有粉丝",
);
const socialEmptyCopy = computed(() =>
  isOwnProfile.value
    ? "当关注关系建立后，这里会成为你的成员导航。"
    : "这里暂时没有公开可展示的关注关系。",
);
const accountSettingsBusy = computed(
  () =>
    changePasswordMutation.isPending.value ||
    requestEmailChangeMutation.isPending.value ||
    confirmEmailChangeMutation.isPending.value,
);

watch(
  [profile, () => currentUserQuery.data.value],
  ([value, currentUser]) => {
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
    if (currentUser && currentUser.username === value.username) {
      profileDraft.interface_theme =
        currentUser.interface_theme === "light" || currentUser.interface_theme === "colorful"
          ? (currentUser.interface_theme as InterfaceTheme)
          : "system";
      profileDraft.locale = currentUser.locale === "en-US" ? "en-US" : "zh-CN";
    }
  },
  { immediate: true },
);

watch(
  [routePanel, isOwnProfile, canViewRelationshipLists, profile],
  ([nextPanel, ownProfile, canViewLists, loadedProfile]) => {
    if (!loadedProfile) {
      return;
    }

    if (nextPanel === "profile" || nextPanel === "account") {
      activeProfilePanel.value = ownProfile ? nextPanel : "topics";
      return;
    }

    if (nextPanel === "topics") {
      activeProfilePanel.value = "topics";
      return;
    }

    if (!ownProfile && (activeProfilePanel.value === "profile" || activeProfilePanel.value === "account")) {
      activeProfilePanel.value = "topics";
    }

    if (!canViewLists && activeProfilePanel.value === "social") {
      activeProfilePanel.value = "topics";
    }
  },
  { immediate: true },
);

// roleLabel 用途：把后端角色值转换为中文展示文案；参数为角色枚举字符串，返回标签文案且无副作用。
function roleLabel(role: string): string {
  const labels: Record<string, string> = {
    admin: "管理员",
    moderator: "版主",
    user: "成员",
  };

  return labels[role] ?? role;
}

// statusLabel 用途：把后端账号状态转换为中文展示文案；参数为状态枚举字符串，返回标签文案且无副作用。
function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    active: "正常",
    silenced: "禁言中",
    suspended: "暂停",
    deleted: "已注销",
  };

  return labels[status] ?? status;
}

// profilePanelRoute 用途：把个人中心设置面板映射到稳定路由；参数为面板 key，返回路由目标或 null 且无副作用。
function profilePanelRoute(panel: ProfilePanel): RouteLocationRaw | null {
  if (!isOwnProfile.value) {
    return null;
  }

  if (panel === "profile") {
    return { name: "account-profile" };
  }

  if (panel === "account") {
    return { name: "account-settings" };
  }

  if (panel === "topics" && isAccountRoute.value) {
    return { name: "account-home" };
  }

  return null;
}

// selectProfilePanel 用途：切换个人中心主面板并在设置页保持稳定 URL；参数为目标面板，副作用是更新本地面板或触发路由跳转。
async function selectProfilePanel(panel: ProfilePanel) {
  const targetRoute = profilePanelRoute(panel);
  if (targetRoute) {
    await router.push(targetRoute);
    if (panel !== "topics") {
      return;
    }
  }

  if (isOwnProfile.value && isAccountRoute.value && route.name !== "account-home" && panel !== "profile" && panel !== "account") {
    await router.push({ name: "account-home" });
  }

  activeProfilePanel.value = panel;
}

// handleMobileBack 用途：移动端资料页返回按钮；无参数，副作用是优先浏览器后退，缺少历史时返回首页。
function handleMobileBack() {
  if (window.history.length > 1) {
    router.back();
    return;
  }

  void router.push({ name: "home" });
}

// openAvatarPicker 用途：打开头像上传文件选择器；无参数，副作用是触发隐藏 input 的点击。
function openAvatarPicker() {
  if (avatarMutation.isPending.value) {
    return;
  }

  avatarInput.value?.click();
}

// requireLogin 用途：社交操作前确认登录状态；无参数，未登录时跳转登录并返回 true，已登录返回 false。
function requireLogin() {
  if (hasAccessToken()) {
    return false;
  }

  void router.push({ name: "auth", query: { redirect: route.fullPath } });
  return true;
}

// toggleRelationship 用途：关注、忽略或屏蔽公开成员；参数为关系类型和目标开关状态，副作用是调用关系接口并更新提示。
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

// openMessageForm 用途：展开私信创建表单；无参数，副作用是预填标题并显示表单，未登录时跳转登录。
function openMessageForm() {
  if (!profile.value || isOwnProfile.value || requireLogin()) {
    return;
  }

  messageTitle.value = `和 ${profile.value.username} 的私信`;
  messageFormOpen.value = true;
}

// sendPrivateMessage 用途：创建与当前成员的私信主题；无参数，副作用是调用私信接口、清理表单并跳转到主题。
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

// saveProfile 用途：保存当前账号的公开资料和界面偏好；无参数，副作用是调用资料接口、刷新缓存和本地偏好。
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
    setLocale(profileDraft.locale);
    setInterfaceTheme(profileDraft.interface_theme);
    await activeProfileQuery.value.refetch();
    profileStatus.value = "资料设置已保存。";
  } catch (error) {
    profileStatus.value = profileErrorMessage(error);
  }
}

// submitPasswordChange 用途：在个人中心提交密码修改；读取当前密码和两次新密码输入，成功后清空密码字段并展示状态。
// 关键参数：无显式参数，依赖当前表单响应式状态；返回值为空，副作用是调用密码修改接口并更新本地提示文案。
async function submitPasswordChange() {
  passwordError.value = "";
  passwordStatus.value = "";
  if (!currentPassword.value || newPassword.value.length < 8) {
    passwordError.value = "请输入当前密码，并确保新密码至少 8 位。";
    return;
  }

  if (newPassword.value !== confirmNewPassword.value) {
    passwordError.value = "两次输入的新密码不一致。";
    return;
  }

  try {
    await changePasswordMutation.mutateAsync({
      current_password: currentPassword.value,
      new_password: newPassword.value,
    });
    currentPassword.value = "";
    newPassword.value = "";
    confirmNewPassword.value = "";
    passwordStatus.value = "密码已更新。";
  } catch (error) {
    passwordError.value = accountErrorMessage(error, "密码修改失败，请稍后再试。");
  }
}

// requestEmailChange 用途：请求登录邮箱变更确认令牌；读取新邮箱和当前密码，成功后提示用户查收令牌。
// 关键参数：无显式参数，依赖邮箱表单响应式状态；返回值为空，副作用是调用邮箱变更请求接口并清空密码输入。
async function requestEmailChange() {
  emailError.value = "";
  emailStatus.value = "";
  if (!newEmail.value.trim() || !emailPassword.value) {
    emailError.value = "请输入新邮箱和当前密码。";
    return;
  }

  try {
    const response = await requestEmailChangeMutation.mutateAsync({
      new_email: newEmail.value.trim(),
      password: emailPassword.value,
    });
    emailPassword.value = "";
    emailStatus.value = `确认令牌已发送至 ${response.email}，请查收后在下方输入。`;
  } catch (error) {
    emailError.value = accountErrorMessage(error, "邮箱变更请求失败，请稍后再试。");
  }
}

// confirmEmailChange 用途：确认登录邮箱变更；读取邮件令牌，成功后清空邮箱草稿并刷新当前用户缓存。
// 关键参数：无显式参数，依赖邮箱确认表单状态；返回值为空，副作用是调用邮箱确认接口并更新页面提示。
async function confirmEmailChange() {
  emailError.value = "";
  emailStatus.value = "";
  if (!emailToken.value.trim()) {
    emailError.value = "请输入邮箱确认令牌。";
    return;
  }

  try {
    const user = await confirmEmailChangeMutation.mutateAsync({ token: emailToken.value.trim() });
    emailToken.value = "";
    newEmail.value = "";
    emailStatus.value = `邮箱已更新为 ${user.email}。`;
  } catch (error) {
    emailError.value = accountErrorMessage(error, "邮箱确认失败，请检查令牌。");
  }
}

// handleAvatarChange 用途：处理头像文件选择结果；参数为 input change 事件，副作用是上传头像并刷新个人资料。
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
    await activeProfileQuery.value.refetch();
    avatarStatus.value = "头像已更新。";
  } catch (error) {
    avatarStatus.value = avatarErrorMessage(error);
  }
}

// accountErrorMessage 用途：把账号设置接口错误转换成用户可读文案；参数为异常对象和兜底文案，返回错误字符串且无副作用。
function accountErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    if (error.code === "invalid_credentials") {
      return "当前密码不正确。";
    }

    if (error.code === "invalid_email_change_token") {
      return "邮箱确认令牌无效或已过期。";
    }

    if (error.code === "email_exists") {
      return "该邮箱已被其他账号使用。";
    }

    if (error.code === "validation_error") {
      return "输入格式不正确，请检查后重试。";
    }
  }

  return error instanceof Error && error.message ? error.message : fallback;
}

// avatarErrorMessage 用途：把头像上传错误转换成用户可读文案；参数为异常对象，返回错误字符串且无副作用。
function avatarErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === "avatar_must_be_image") {
      return "头像必须是 PNG、JPG、GIF 或 WebP 图片。";
    }
    if (error.code === "upload_too_large") {
      const maxBytes = typeof error.details.max_bytes === "number" ? error.details.max_bytes : null;
      const limit = maxBytes ? `${(maxBytes / 1024 / 1024).toFixed(maxBytes >= 1024 * 1024 ? 1 : 2)} MB` : "2 MB";
      return `头像文件超过 ${limit} 限制，请压缩或裁剪后再上传。`;
    }
  }

  return "头像上传失败，请确认已登录且文件类型安全。";
}

// profileErrorMessage 用途：把资料保存错误转换成用户可读文案；参数为异常对象，返回错误字符串且无副作用。
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

// socialErrorMessage 用途：把社交接口错误转换成用户可读文案；参数为异常对象，返回错误字符串且无副作用。
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
    <header class="profile-mobile-header" aria-label="移动端个人资料导航">
      <button type="button" aria-label="返回上一页" @click="handleMobileBack">
        <ArrowLeftOutlined aria-hidden="true" />
      </button>
      <div class="profile-mobile-header__actions">
        <RouterLink :to="{ name: 'search' }" aria-label="搜索">
          <SearchOutlined aria-hidden="true" />
        </RouterLink>
        <button type="button" aria-label="更多操作">
          <EllipsisOutlined aria-hidden="true" />
        </button>
      </div>
    </header>

    <UiCard class="profile-hero">
      <div v-if="isProfileLoading" class="profile-state">正在加载用户资料…</div>
      <div v-else-if="isProfileError" class="profile-state profile-state--error" role="alert">
        用户资料暂时不可用。请稍后重试，或确认用户是否存在。
      </div>
      <template v-else-if="profile">
        <div class="profile-hero__main">
          <div class="profile-identity-card">
            <div class="profile-avatar-panel">
              <div class="profile-avatar-frame">
                <UiAvatar
                  :name="profile.username"
                  :src="resolveApiAssetUrl(profile.avatar_url)"
                  :role="null"
                  :level="null"
                  size="lg"
                />
                <span class="profile-avatar-status" aria-hidden="true"></span>
                <input
                  v-if="isOwnProfile"
                  ref="avatarInput"
                  class="avatar-upload__input"
                  type="file"
                  accept="image/png,image/jpeg,image/gif,image/webp"
                  @change="handleAvatarChange"
                />
              </div>
              <div v-if="isOwnProfile" class="avatar-upload">
                <UiButton type="button" tone="ghost" @click="openAvatarPicker">
                  {{ avatarMutation.isPending.value ? "上传中…" : "更换头像" }}
                </UiButton>
                <span v-if="avatarStatus" role="status">{{ avatarStatus }}</span>
              </div>
            </div>

            <div class="profile-copy">
              <div class="profile-kicker">
                <UiBadge tone="blue">{{ isAccountRoute ? "个人中心" : "公开资料" }}</UiBadge>
                <UiBadge tone="green">{{ roleLabel(profile.role) }}</UiBadge>
                <UiBadge tone="blue" :title="`社区等级 ${profile.level}，由参与和贡献累计提升。`">等级 {{ profile.level }}</UiBadge>
                <UiBadge tone="amber" :title="`信任等级 ${profile.trust_level}：${profile.trust_level_label}`">信任 {{ profile.trust_level }}</UiBadge>
                <span class="profile-status">
                  <span class="profile-status__dot"></span>
                  {{ statusLabel(profile.status) }}
                </span>
              </div>
              <h1>{{ displayName }}</h1>
              <p class="profile-meta">
                @{{ profile.username }} · 加入 {{ joinedAt }} · {{ profileVisibilityLabel(profile.profile_visibility) }}
              </p>
              <p v-if="profileSummary" class="profile-summary">{{ profileSummary }}</p>
              <p v-else-if="isOwnProfile" class="profile-summary profile-summary--empty">
                这里还没有简介。写一句话，别人打开你的公开资料时会更快知道你关注什么。
              </p>
              <p v-else class="profile-summary profile-summary--empty">
                这个成员还没有填写简介。
              </p>
              <div v-if="profile.website_url || profile.location" class="profile-links">
                <a v-if="profile.website_url" :href="profile.website_url" target="_blank" rel="noopener noreferrer">
                  {{ profile.website_url }}
                </a>
                <span v-if="profile.location">{{ profile.location }}</span>
              </div>
            </div>
          </div>

          <dl class="profile-stats" aria-label="用户内容统计">
            <div v-for="stat in profileStats" :key="stat.label">
              <dt>
                {{ stat.label }}
                <span class="profile-stat-icon">
                  <component :is="stat.icon" aria-hidden="true" />
                </span>
              </dt>
              <dd>{{ stat.value }}</dd>
              <span class="profile-stat-note">{{ stat.note }}</span>
            </div>
          </dl>
        </div>

        <div class="profile-hero__footer">
          <div class="profile-insights" aria-label="账号概览">
            <div class="profile-insight">
              <span>成长</span>
              <strong>等级 {{ profile.level }} · {{ profile.points_balance }} 可用积分</strong>
              <div class="profile-level-meter" :style="levelProgressStyle" aria-hidden="true">
                <span></span>
              </div>
              <small>{{ profile.experience_total }} 经验 · {{ levelProgressPercent }}%</small>
            </div>
            <div class="profile-insight profile-insight--trust">
              <span>信任</span>
              <strong>信任等级 {{ profile.trust_level }} · {{ profile.trust_level_label }}</strong>
              <div v-if="profileBadges.length" class="profile-badges-list">
                <span v-for="badge in profileBadges.slice(0, 3)" :key="badge.id" class="profile-badge-chip">
                  <em>{{ badge.icon }}</em>
                  {{ badge.name }}
                </span>
              </div>
            </div>
          </div>

          <div v-if="isOwnProfile" class="profile-primary-actions" aria-label="个人中心快捷操作">
            <RouterLink class="profile-action-link profile-action-link--primary" :to="{ name: 'account-profile' }">
              编辑资料
            </RouterLink>
            <RouterLink class="profile-action-link" :to="{ name: 'account-settings' }">
              账号设置
            </RouterLink>
            <RouterLink class="profile-action-link" :to="{ name: 'account-preferences' }">
              邮件偏好
            </RouterLink>
          </div>
          <div v-else class="profile-public-actions" aria-label="用户社交操作">
            <p class="profile-relationship-copy">关系状态：{{ socialSummary }}</p>
            <div class="profile-primary-actions profile-primary-actions--social">
              <UiButton
                type="button"
                :tone="relationship?.following ? 'success' : 'primary'"
                :disabled="relationshipMutation.isPending.value || relationship?.blocked"
                @click="toggleRelationship('follow', !relationship?.following)"
              >
                {{ relationship?.blocked ? "已屏蔽" : relationship?.following ? "已关注" : "关注" }}
              </UiButton>
              <UiButton type="button" tone="subtle" @click="openMessageForm">私信</UiButton>
              <UiButton
                type="button"
                tone="ghost"
                :disabled="relationshipMutation.isPending.value"
                @click="toggleRelationship('ignore', !relationship?.ignored)"
              >
                {{ relationship?.ignored ? "取消忽略" : "忽略" }}
              </UiButton>
              <UiButton
                type="button"
                tone="ghost"
                :disabled="relationshipMutation.isPending.value"
                @click="toggleRelationship('block', !relationship?.blocked)"
              >
                {{ relationship?.blocked ? "取消屏蔽" : "屏蔽" }}
              </UiButton>
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

    <div v-if="profile" class="profile-content-layout">
      <main class="profile-content-main">
        <nav class="profile-section-switcher" aria-label="个人中心内容">
          <button
            v-for="panel in profilePanels"
            :key="panel.key"
            type="button"
            :class="{ active: activeProfilePanel === panel.key }"
            @click="selectProfilePanel(panel.key)"
          >
            {{ panel.label }}
          </button>
        </nav>

    <section v-if="profile && activeProfilePanel === 'topics'" class="profile-topics" aria-labelledby="profile-topics-title">
      <header>
        <div>
          <h2 id="profile-topics-title">公开主题</h2>
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
          <p>等第一篇主题发布后，这里会变成一条清晰的个人讨论时间线。</p>
        </div>
        <RouterLink class="profile-empty__link" to="/boards">去看看版块</RouterLink>
      </UiCard>
      <TopicList
        v-else
        :topics="topicsQuery.data.value"
        :can-delete-topics="canDeleteTopics"
        :deleting-topic-id="deletingTopicId"
        @delete-topic="requestDeleteTopic"
      />
    </section>

    <section v-else-if="profile && activeProfilePanel === 'activity'" class="profile-activity" aria-labelledby="profile-activity-title">
      <header>
        <div>
          <h2 id="profile-activity-title">公开活动</h2>
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

    <section
      v-else-if="profile && activeProfilePanel === 'social'"
      class="profile-social-section"
      aria-labelledby="profile-social-title"
    >
      <header>
        <div>
          <h2 id="profile-social-title">{{ socialPanelTitle }}</h2>
        </div>
        <div class="profile-social-tabs" aria-label="关注列表类型">
          <UiButton
            type="button"
            :tone="socialListKind === 'following' ? 'primary' : 'ghost'"
            @click="socialListKind = 'following'"
          >
            {{ socialFollowingLabel }} · {{ profile.following_count }}
          </UiButton>
          <UiButton
            type="button"
            :tone="socialListKind === 'followers' ? 'primary' : 'ghost'"
            @click="socialListKind = 'followers'"
          >
            {{ socialFollowersLabel }} · {{ profile.follower_count }}
          </UiButton>
        </div>
      </header>

      <UiCard v-if="!canViewRelationshipLists" class="profile-state">关注关系暂时不可见。</UiCard>
      <UiCard v-else-if="relationshipUsersQuery.isLoading.value" class="profile-state">正在加载关注关系…</UiCard>
      <UiCard v-else-if="relationshipUsersQuery.isError.value" class="profile-state profile-state--error" role="alert">
        暂时无法读取关注关系，请稍后重试。
      </UiCard>
      <div v-else-if="relationshipUsers.length" class="profile-social-list">
        <RouterLink
          v-for="relatedUser in relationshipUsers"
          :key="relatedUser.id"
          class="profile-social-user"
          :to="{ name: 'user-profile', params: { id: relatedUser.id } }"
        >
          <UiAvatar
            :name="relatedUser.display_name?.trim() || relatedUser.username"
            :src="resolveApiAssetUrl(relatedUser.avatar_url)"
            :role="relatedUser.role"
            :level="relatedUser.level"
            size="md"
          />
          <div>
            <strong>{{ relatedUser.display_name?.trim() || relatedUser.username }}</strong>
            <p>
              @{{ relatedUser.username }} · 等级 {{ relatedUser.level }} ·
              {{ relatedUser.topic_count }} 主题 / {{ relatedUser.post_count }} 回复
            </p>
          </div>
          <span>{{ relativeTime(relatedUser.followed_at) }}</span>
        </RouterLink>
      </div>
      <UiCard v-else class="profile-empty">
        <span class="profile-empty__mark">∅</span>
        <div>
          <strong>{{ socialEmptyTitle }}</strong>
          <p>{{ socialEmptyCopy }}</p>
        </div>
      </UiCard>
    </section>

    <section
      v-else-if="profile && isOwnProfile && activeProfilePanel === 'profile'"
      class="profile-settings-section"
      aria-labelledby="profile-settings-title"
    >
      <header>
        <div>
          <h2 id="profile-settings-title">资料设置</h2>
          <p>管理公开昵称、简介、个人链接、可见范围和界面偏好。</p>
        </div>
      </header>

      <UiCard class="profile-settings-card">
        <div class="profile-settings-card__head">
          <span>公开资料</span>
          <strong>别人看到的你</strong>
          <p>这些内容会出现在公开成员页和讨论上下文里。</p>
        </div>
        <p v-if="profileStatus" class="profile-form-status" role="status">{{ profileStatus }}</p>
        <div class="profile-settings-form">
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
          </div>
        </div>
      </UiCard>
    </section>

    <section
      v-else-if="profile && isOwnProfile && activeProfilePanel === 'account'"
      class="profile-settings-section"
      aria-labelledby="profile-account-title"
    >
      <header>
        <div>
          <h2 id="profile-account-title">账号设置</h2>
          <p>只保留密码和登录邮箱；二次验证、活跃会话、OAuth / SSO 暂不展示。</p>
        </div>
      </header>

      <UiCard class="profile-settings-card profile-settings-card--account">
        <div class="profile-settings-card__head">
          <span>登录安全</span>
          <strong>密码与邮箱</strong>
          <p>当前登录邮箱：{{ currentUserQuery.data.value?.email }}</p>
        </div>
        <div class="profile-account-grid">
          <form class="profile-account-form" @submit.prevent="submitPasswordChange">
            <header>
              <h3>修改密码</h3>
              <p>请使用至少 8 位的新密码。</p>
            </header>
            <label>
              <span>当前密码</span>
              <PasswordField v-model="currentPassword" autocomplete="current-password" />
            </label>
            <label>
              <span>新密码</span>
              <PasswordField v-model="newPassword" autocomplete="new-password" />
            </label>
            <label>
              <span>确认新密码</span>
              <PasswordField v-model="confirmNewPassword" autocomplete="new-password" />
            </label>
            <p v-if="passwordError" class="profile-form-status profile-form-status--error" role="alert">
              {{ passwordError }}
            </p>
            <p v-if="passwordStatus" class="profile-form-status" role="status">{{ passwordStatus }}</p>
            <UiButton type="submit" tone="primary" :disabled="accountSettingsBusy">保存密码</UiButton>
          </form>

          <div class="profile-account-form">
            <header>
              <h3>修改邮箱</h3>
              <p>确认令牌会发送到新邮箱。</p>
            </header>
            <form class="profile-account-subform" @submit.prevent="requestEmailChange">
              <label>
                <span>新邮箱</span>
                <input v-model="newEmail" type="email" autocomplete="email" />
              </label>
              <label>
                <span>当前密码</span>
                <PasswordField v-model="emailPassword" autocomplete="current-password" />
              </label>
              <UiButton type="submit" tone="primary" :disabled="accountSettingsBusy">发送确认令牌</UiButton>
            </form>
            <form class="profile-account-subform profile-account-subform--confirm" @submit.prevent="confirmEmailChange">
              <label>
                <span>邮箱确认令牌</span>
                <input v-model="emailToken" autocomplete="one-time-code" />
              </label>
              <UiButton type="submit" tone="subtle" :disabled="accountSettingsBusy">确认邮箱变更</UiButton>
            </form>
            <p v-if="emailError" class="profile-form-status profile-form-status--error" role="alert">
              {{ emailError }}
            </p>
            <p v-if="emailStatus" class="profile-form-status" role="status">{{ emailStatus }}</p>
          </div>
        </div>
      </UiCard>
    </section>
      </main>

      <aside class="profile-sidebar" aria-label="个人资料侧栏">
        <UiCard class="profile-side-card profile-side-card--badges">
          <header>
            <h2>个人勋章</h2>
            <TrophyOutlined aria-hidden="true" />
          </header>
          <div v-if="profileBadges.length" class="profile-side-badges">
            <span v-for="badge in profileBadges.slice(0, 6)" :key="badge.id" :title="badge.description">
              <em>{{ badge.icon }}</em>
              <strong>{{ badge.name }}</strong>
            </span>
          </div>
          <p v-else class="profile-side-empty">还没有公开勋章。</p>
          <span class="profile-side-mobile-copy">
            查看全部 {{ profileBadges.length }} 个勋章
          </span>
          <span v-if="profileBadges.length > 6" class="profile-side-link profile-side-link--muted">
            已展示 6 / {{ profileBadges.length }} 个勋章
          </span>
        </UiCard>

        <UiCard class="profile-side-card">
          <header>
            <h2>参与版块</h2>
            <FileTextOutlined aria-hidden="true" />
          </header>
          <div v-if="topicsQuery.isLoading.value" class="profile-side-empty">正在读取版块…</div>
          <div v-else-if="activeBoardSummaries.length" class="profile-board-list">
            <RouterLink
              v-for="board in activeBoardSummaries"
              :key="board.slug"
              :to="{ name: 'board-detail', params: { slug: board.slug } }"
            >
              <span class="profile-board-dot" :style="{ backgroundColor: board.color }" aria-hidden="true"></span>
              <strong>{{ board.name }}</strong>
              <em>{{ board.topicCount }} 主题 · {{ board.replyCount }} 回复</em>
            </RouterLink>
          </div>
          <p v-else class="profile-side-empty">发布主题后，这里会展示真实参与过的版块。</p>
          <span class="profile-side-mobile-copy">查看全部参与的版块</span>
          <RouterLink class="profile-side-link" to="/boards">查看全部版块</RouterLink>
        </UiCard>
      </aside>

      <RouterLink class="profile-mobile-publish" :to="{ name: 'new-topic' }">
        <EditFilled aria-hidden="true" />
        <span>发布主题</span>
      </RouterLink>

      <nav class="profile-mobile-bottom-nav" aria-label="移动端主导航">
        <RouterLink :to="{ name: 'home' }">
          <HomeOutlined aria-hidden="true" />
          <span>首页</span>
        </RouterLink>
        <RouterLink :to="{ name: 'board-directory' }">
          <CompassOutlined aria-hidden="true" />
          <span>发现</span>
        </RouterLink>
        <RouterLink class="profile-mobile-bottom-nav__create" :to="{ name: 'new-topic' }" aria-label="发布主题">
          <span class="profile-mobile-bottom-nav__plus" aria-hidden="true"></span>
        </RouterLink>
        <RouterLink :to="{ name: 'messages' }">
          <BellOutlined aria-hidden="true" />
          <span>消息</span>
        </RouterLink>
        <RouterLink :to="{ name: 'account-home' }">
          <UserOutlined aria-hidden="true" />
          <span>我的</span>
        </RouterLink>
      </nav>
    </div>
  </div>
</template>

<style scoped lang="scss" src="./UserProfilePage.scss"></style>
