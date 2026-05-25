<script setup lang="ts">
import { MessageOutlined, PlusOutlined, SendOutlined } from "@ant-design/icons-vue";
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { useCurrentUser } from "@/features/auth/queries";
import { channelTypeLabel } from "@/features/chat/model";
import type { ChatChannel, ChatMessage } from "@/features/chat/model";
import {
  useChatChannels,
  useChatMessages,
  useChatPresence,
  useChatStream,
  useCreateChatChannel,
  useSendChatMessage,
  useUpdateChatPresence,
} from "@/features/chat/queries";
import { hasAccessToken } from "@/shared/api/client";
import { relativeTime } from "@/shared/lib/format";
import UiBadge from "@/shared/ui/Badge.vue";
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";

const route = useRoute();
const router = useRouter();
const currentUserQuery = useCurrentUser();
const hasStoredToken = hasAccessToken();
const currentUser = computed(() => currentUserQuery.data.value);
const canUseChat = computed(() => Boolean(currentUser.value));
const isCheckingSession = computed(() => hasStoredToken && currentUserQuery.isPending.value);
const selectedChannelId = ref(String(route.query.channel ?? ""));
const draft = ref("");
const searchTerm = ref("");

const channelsQuery = useChatChannels(canUseChat);
const channels = computed(() => channelsQuery.data.value ?? []);
const activeChannel = computed(
  () => channels.value.find((channel) => channel.id === selectedChannelId.value) ?? null,
);
const activeChannelId = computed(() => activeChannel.value?.id ?? "");
const messagesQuery = useChatMessages(activeChannelId, searchTerm);
const messages = computed(() => messagesQuery.data.value?.messages ?? []);
const presenceQuery = useChatPresence(activeChannelId);
const presence = computed(() => presenceQuery.data.value ?? []);
const typingUsers = computed(() =>
  presence.value
    .filter((item) => item.typing && item.user.id !== currentUser.value?.id)
    .map((item) => item.user.username),
);
const createChannel = useCreateChatChannel();
const sendMessage = useSendChatMessage(activeChannelId);
const updatePresence = useUpdateChatPresence(activeChannelId);
useChatStream(activeChannelId, computed(() => canUseChat.value && Boolean(activeChannelId.value)));

watch(
  channels,
  (items) => {
    if (!items.length) {
      selectedChannelId.value = "";
      return;
    }
    if (!items.some((channel) => channel.id === selectedChannelId.value)) {
      selectChannel(items[0]);
    }
  },
  { immediate: true },
);

watch(
  activeChannelId,
  (channelId) => {
    if (channelId) {
      updatePresence.mutate({ status: "online", typing: false });
    }
  },
  { immediate: true },
);

function selectChannel(channel: ChatChannel) {
  selectedChannelId.value = channel.id;
  void router.replace({ query: { ...route.query, channel: channel.id } });
}

function createDefaultChannel() {
  createChannel.mutate(
    {
      name: "站内大厅",
      description: "所有成员都可以加入的实时交流频道。",
      channel_type: "public",
      slug: "general",
    },
    {
      onSuccess: (channel) => {
        selectChannel(channel);
      },
    },
  );
}

function submitMessage() {
  const rawText = draft.value.trim();
  if (!rawText || !activeChannelId.value) {
    return;
  }
  sendMessage.mutate(
    { raw_text: rawText },
    {
      onSuccess: () => {
        draft.value = "";
        updatePresence.mutate({ status: "online", typing: false });
      },
    },
  );
}

function markTyping() {
  if (activeChannelId.value && draft.value.trim()) {
    updatePresence.mutate({ status: "online", typing: true });
  }
}

function messageAuthor(message: ChatMessage): string {
  return message.user.username === currentUser.value?.username ? "我" : message.user.username;
}
</script>

<template>
  <div class="chat-page">
    <UiCard class="chat-hero">
      <span class="chat-orbit" aria-hidden="true"></span>
      <div>
        <UiBadge tone="green">Realtime</UiBadge>
        <h1>实时 Chat 与在线状态</h1>
        <p>频道消息、版块权限、在线成员和输入状态统一在一个轻量实时面板中。</p>
      </div>
    </UiCard>

    <UiCard v-if="isCheckingSession" class="chat-state">正在确认登录状态…</UiCard>

    <UiCard v-else-if="!currentUser" class="chat-state">
      <strong>登录后进入实时频道</strong>
      <p>Chat 会显示在线状态和历史消息，需要先确认身份。</p>
      <RouterLink to="/auth?redirect=/chat">前往登录</RouterLink>
    </UiCard>

    <section v-else class="chat-layout">
      <UiCard class="channel-panel">
        <div class="panel-heading">
          <div>
            <span>频道</span>
            <strong>{{ channels.length }} 个可访问频道</strong>
          </div>
          <button
            class="icon-action"
            type="button"
            :disabled="createChannel.isPending.value"
            aria-label="创建默认大厅频道"
            @click="createDefaultChannel"
          >
            <PlusOutlined />
          </button>
        </div>

        <div v-if="channelsQuery.isLoading.value" class="channel-state">正在同步频道…</div>
        <div v-else-if="channelsQuery.isError.value" class="channel-state channel-state--error">
          频道暂时不可用。
        </div>
        <div v-else-if="!channels.length" class="channel-state">
          <p>还没有可访问频道。</p>
          <UiButton tone="primary" @click="createDefaultChannel">创建站内大厅</UiButton>
        </div>
        <button
          v-for="channel in channels"
          v-else
          :key="channel.id"
          class="channel-item"
          :class="{ active: channel.id === activeChannelId }"
          type="button"
          @click="selectChannel(channel)"
        >
          <MessageOutlined />
          <span>
            <strong>{{ channel.name }}</strong>
            <small>{{ channelTypeLabel(channel) }} · {{ channel.message_count }} 条消息</small>
          </span>
        </button>
      </UiCard>

      <UiCard class="chat-room">
        <header class="room-header">
          <div>
            <span class="room-kicker">{{ activeChannel ? channelTypeLabel(activeChannel) : "请选择频道" }}</span>
            <h2>{{ activeChannel?.name ?? "实时频道" }}</h2>
            <p>{{ activeChannel?.description ?? "选择左侧频道后即可查看历史消息并参与实时讨论。" }}</p>
          </div>
          <div class="presence-strip" aria-label="在线成员">
            <span v-for="item in presence" :key="item.user.id" :class="{ typing: item.typing }">
              {{ item.user.username }}
            </span>
          </div>
        </header>

        <a-input
          v-model:value="searchTerm"
          class="chat-search"
          placeholder="搜索当前频道历史消息"
          allow-clear
        />

        <div v-if="messagesQuery.isLoading.value" class="message-state">正在加载历史消息…</div>
        <div v-else-if="messagesQuery.isError.value" class="message-state message-state--error">
          无法读取该频道，可能没有权限或频道已不存在。
        </div>
        <div v-else-if="!messages.length" class="message-state">
          暂无消息，发出第一条实时消息吧。
        </div>
        <ol v-else class="message-list" aria-label="聊天消息">
          <li
            v-for="message in messages"
            :key="message.id"
            class="message-bubble"
            :class="{ mine: message.user.id === currentUser.id }"
          >
            <div class="message-meta">
              <strong>{{ messageAuthor(message) }}</strong>
              <time :datetime="message.created_at">{{ relativeTime(message.created_at) }}</time>
            </div>
            <p>{{ message.raw_text }}</p>
          </li>
        </ol>

        <p v-if="typingUsers.length" class="typing-line">
          {{ typingUsers.join("、") }} 正在输入…
        </p>

        <form class="composer" @submit.prevent="submitMessage">
          <a-textarea
            v-model:value="draft"
            :disabled="!activeChannelId || sendMessage.isPending.value"
            placeholder="输入实时消息，Enter 发送，Shift+Enter 换行"
            :auto-size="{ minRows: 2, maxRows: 5 }"
            @input="markTyping"
            @press-enter.exact.prevent="submitMessage"
          />
          <UiButton type="submit" tone="primary">
            <template #icon>
              <SendOutlined />
            </template>
            发送
          </UiButton>
        </form>
      </UiCard>
    </section>
  </div>
</template>

<style scoped lang="scss" src="./ChatPage.scss"></style>
