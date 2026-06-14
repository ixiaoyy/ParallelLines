<script setup lang="ts">
import { Badge as ABadge } from "ant-design-vue";
import { BellFilled, CheckCircleOutlined, InboxOutlined } from "@ant-design/icons-vue";
import { computed, ref } from "vue";

import { toNotificationItem } from "@/features/notifications/model";
import {
  useMarkNotificationsRead,
  useNotificationList,
  useNotificationsStream,
} from "@/features/notifications/queries";
import { useOutsidePointerDown } from "@/shared/lib/useOutsidePointerDown";

const open = ref(false);
const bellRef = ref<HTMLElement | null>(null);
const notificationsQuery = useNotificationList();
const markRead = useMarkNotificationsRead();
useNotificationsStream();

const unreadCount = computed(() => notificationsQuery.data.value?.unread_count ?? 0);
const notifications = computed(() =>
  (notificationsQuery.data.value?.notifications ?? []).map(toNotificationItem),
);
const hasNotifications = computed(() => notifications.value.length > 0);
const streamStateLabel = computed(() => (notificationsQuery.isFetching.value ? "同步中" : "实时"));
const markReadPending = computed(() => markRead.isPending.value);

function togglePanel() {
  open.value = !open.value;
}

function closePanel() {
  open.value = false;
}

function markAllRead() {
  markRead.mutate(undefined);
}

function markOneRead(id: string) {
  markRead.mutate([id]);
}

function openNotification(id: string, unread: boolean) {
  if (unread) {
    markOneRead(id);
  }
  closePanel();
}

useOutsidePointerDown(bellRef, closePanel, () => open.value);
</script>

<template>
  <div ref="bellRef" class="notification-bell" @keydown.esc="closePanel">
    <ABadge :count="unreadCount" :number-style="{ backgroundColor: '#ef4444' }">
      <button
        class="notification-trigger"
        type="button"
        :aria-label="`通知，${unreadCount} 条未读`"
        :aria-expanded="open"
        aria-haspopup="dialog"
        @click="togglePanel"
      >
        <BellFilled />
      </button>
    </ABadge>

    <section v-if="open" class="notification-panel" role="dialog" aria-label="通知中心">
      <header class="notification-panel__header">
        <div>
          <span class="panel-kicker">{{ streamStateLabel }}</span>
          <h2>通知中心</h2>
        </div>
        <button
          type="button"
          class="mark-all"
          :disabled="unreadCount === 0 || markReadPending"
          @click="markAllRead"
        >
          <CheckCircleOutlined />
          全部已读
        </button>
      </header>

      <div v-if="notificationsQuery.isError.value" class="notification-empty notification-empty--error" role="alert">
        <InboxOutlined />
        <strong>通知暂时不可用</strong>
        <span>请稍后重试。</span>
      </div>

      <div v-else-if="hasNotifications" class="notification-list" aria-live="polite">
        <article
          v-for="item in notifications"
          :key="item.id"
          class="notification-card"
          :class="[`notification-card--${item.tone}`, { unread: item.unread }]"
        >
          <RouterLink class="notification-link" :to="item.targetUrl" @click="openNotification(item.id, item.unread)">
            <span class="notification-dot" aria-hidden="true"></span>
            <span class="notification-copy">
              <strong>{{ item.title }}</strong>
              <span>{{ item.description }}</span>
              <small>{{ item.relativeCreatedAt }}</small>
            </span>
          </RouterLink>
          <button
            v-if="item.unread"
            type="button"
            class="mark-one"
            :aria-label="`将通知 ${item.title} 标记为已读`"
            @click="markOneRead(item.id)"
          >
            已读
          </button>
        </article>
      </div>

      <div v-else class="notification-empty">
        <InboxOutlined />
        <strong>暂时没有新通知</strong>
        <span>回复、提及和关注版块动态会在这里出现。</span>
      </div>
    </section>
  </div>
</template>

<style scoped lang="scss" src="./NotificationBell.scss"></style>
