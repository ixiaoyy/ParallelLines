<script setup lang="ts">
import { computed, ref } from "vue";

import {
  useDeletePushSubscription,
  usePushSubscriptionState,
  useSavePushSubscription,
} from "@/features/pwa/queries";
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";

const stateQuery = usePushSubscriptionState();
const saveSubscription = useSavePushSubscription();
const deleteSubscription = useDeletePushSubscription();
const status = ref("");
const subscription = computed(() => stateQuery.data.value?.subscription ?? null);
const supported = computed(() =>
  typeof window !== "undefined" && "serviceWorker" in navigator && "Notification" in window,
);

async function enablePush() {
  status.value = "";
  if (!supported.value) {
    status.value = "当前浏览器不支持 PWA 推送。";
    return;
  }

  const permission = await Notification.requestPermission();
  if (permission !== "granted") {
    status.value = "你拒绝了浏览器通知权限。";
    return;
  }

  const registration = await navigator.serviceWorker.ready;
  const vapidKey = import.meta.env.VITE_WEB_PUSH_PUBLIC_KEY as string | undefined;
  if (!vapidKey) {
    await registration.showNotification("平行线通知已可用", {
      body: "本机通知已启用；配置 VAPID 公钥后可同步 Web Push 订阅。",
      icon: "/logo-icon.png",
      data: { url: "/notifications" },
    });
    status.value = "本机通知测试已发送；缺少 VAPID 公钥，未创建服务器 Push 订阅。";
    return;
  }

  const browserSubscription = await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToApplicationServerKey(vapidKey),
  });
  const json = browserSubscription.toJSON();
  if (!json.endpoint || !json.keys?.p256dh || !json.keys.auth) {
    status.value = "浏览器返回的订阅缺少密钥。";
    return;
  }

  await saveSubscription.mutateAsync({
    endpoint: json.endpoint,
    keys: { p256dh: json.keys.p256dh, auth: json.keys.auth },
    user_agent: navigator.userAgent,
  });
  await registration.showNotification("平行线推送已开启", {
    body: "以后重要通知会遵守你的通知偏好和免打扰设置。",
    icon: "/logo-icon.png",
    data: { url: "/email-preferences" },
  });
  status.value = "Push 订阅已保存。";
}

async function disablePush() {
  await deleteSubscription.mutateAsync();
  const registration = await navigator.serviceWorker.ready;
  const current = await registration.pushManager.getSubscription();
  await current?.unsubscribe();
  status.value = "Push 订阅已撤销。";
}

function urlBase64ToApplicationServerKey(value: string): ArrayBuffer {
  const padding = "=".repeat((4 - (value.length % 4)) % 4);
  const base64 = `${value}${padding}`.replace(/-/g, "+").replace(/_/g, "/");
  const raw = window.atob(base64);
  const buffer = new ArrayBuffer(raw.length);
  const output = new Uint8Array(buffer);
  for (let index = 0; index < raw.length; index += 1) {
    output[index] = raw.charCodeAt(index);
  }
  return buffer;
}
</script>

<template>
  <UiCard class="push-panel">
    <header>
      <span class="eyebrow">PWA / Web Push</span>
      <h2>{{ subscription ? "推送通知已订阅" : "安装应用并接收推送" }}</h2>
      <p>Service Worker 提供离线页和通知点击跳转；服务器订阅会遵守通知偏好。</p>
    </header>

    <p v-if="!supported" class="push-warning">当前浏览器不支持 Service Worker 或通知权限。</p>
    <p v-else-if="subscription" class="push-state">
      当前设备：{{ subscription.endpoint_excerpt }}
    </p>
    <p v-else class="push-state">未订阅此设备。安装 PWA 后也可以继续使用浏览器通知。</p>

    <div class="push-actions">
      <UiButton tone="subtle" :disabled="saveSubscription.isPending.value || !supported" @click="enablePush">
        {{ saveSubscription.isPending.value ? "开启中…" : "开启推送" }}
      </UiButton>
      <UiButton tone="ghost" :disabled="deleteSubscription.isPending.value || !subscription" @click="disablePush">
        撤销订阅
      </UiButton>
    </div>

    <p v-if="status" class="push-status" role="status">{{ status }}</p>
  </UiCard>
</template>

<style scoped lang="scss" src="./PushNotificationPanel.scss"></style>
