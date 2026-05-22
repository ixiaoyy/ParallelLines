<script setup lang="ts">
import { computed } from "vue";

import { useCurrentUser } from "@/features/auth/queries";
import type { PrivateMessageTopic } from "@/features/social/model";
import { usePrivateMessages } from "@/features/social/queries";
import { hasAccessToken } from "@/shared/api/client";
import { topicDetailPath } from "@/shared/router/topicRoutes";
import UiBadge from "@/shared/ui/Badge.vue";
import UiCard from "@/shared/ui/Card.vue";

const currentUserQuery = useCurrentUser();
const hasStoredToken = hasAccessToken();
const currentUser = computed(() => currentUserQuery.data.value);
const isCheckingSession = computed(() => hasStoredToken && currentUserQuery.isPending.value);
const messagesQuery = usePrivateMessages(computed(() => Boolean(currentUser.value)));
const messages = computed(() => messagesQuery.data.value ?? []);

function participantNames(message: PrivateMessageTopic): string {
  return message.participants
    .filter((participant) => participant.username !== currentUser.value?.username)
    .map((participant) => participant.username)
    .join("、");
}
</script>

<template>
  <div class="messages-page">
    <UiCard class="messages-hero">
      <span class="messages-orbit" aria-hidden="true"></span>
      <div>
        <UiBadge tone="blue">Private Lines</UiBadge>
        <h1>私信主题</h1>
        <p>私信复用主题/楼层体验，但只有参与者可以读取、回复和收到后续通知。</p>
      </div>
    </UiCard>

    <UiCard v-if="isCheckingSession" class="messages-state">
      正在确认登录状态…
    </UiCard>

    <UiCard v-else-if="!currentUser" class="messages-state">
      <strong>登录后查看私信</strong>
      <p>私信主题包含私人上下文，需要先确认身份。</p>
      <RouterLink to="/auth?redirect=/messages">前往登录</RouterLink>
    </UiCard>

    <UiCard v-else-if="messagesQuery.isLoading.value" class="messages-state">
      正在同步你的私信主题…
    </UiCard>

    <UiCard v-else-if="messagesQuery.isError.value" class="messages-state messages-state--error">
      <strong>私信暂时不可用</strong>
      <p>请稍后重试，或从用户资料页重新发起私信。</p>
    </UiCard>

    <UiCard v-else-if="!messages.length" class="messages-state messages-empty">
      <strong>还没有私信主题</strong>
      <p>进入任意成员资料页，点击“私信”即可创建一条只对参与者可见的主题。</p>
    </UiCard>

    <section v-else class="messages-list" aria-label="私信主题列表">
      <RouterLink
        v-for="message in messages"
        :key="message.topic.id"
        class="message-card"
        :class="{ unread: message.unread }"
        :to="topicDetailPath({ id: message.topic.id, slug: message.topic.slug })"
      >
        <span class="message-card__rail" aria-hidden="true"></span>
        <div>
          <span class="message-card__kicker">
            {{ message.unread ? "未读私信" : "已同步" }}
          </span>
          <h2>{{ message.topic.title }}</h2>
          <p>{{ message.topic.excerpt || "这条私信还没有摘要。" }}</p>
          <small>参与者：{{ participantNames(message) || "仅你自己" }}</small>
        </div>
        <strong>#{{ message.topic.reply_count + 1 }}</strong>
      </RouterLink>
    </section>
  </div>
</template>

<style scoped lang="scss" src="./MessagesPage.scss"></style>
