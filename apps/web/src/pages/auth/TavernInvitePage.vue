<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";

import {
  clearTavernInviteFlow, loadTavernInviteFlow, restoreTavernInviteFlow, TAVERN_INVITE_PATH, tavernInviteCaptureVersion,
} from "@/features/auth/tavernInvite";
import { UNIFIED_AUTH_ENABLED } from "@/features/auth/unified/protocol";
import { ensurePrimarySession } from "@/features/auth/unified/session";
import { apiGet, getRefreshToken, hasAccessToken, isAuthenticationError } from "@/shared/api/client";
import { currentLocale, uiText } from "@/shared/i18n/locale";
import UiButton from "@/shared/ui/Button.vue";
import LanguageSwitcher from "@/shared/ui/LanguageSwitcher.vue";
import ChatEntryLoading from "./ChatEntryLoading.vue";

const TEXT = {
  loading: ["正在验证主站登录…", "Checking your ParallelLines sign-in…"],
  heading: ["加入聊天房间", "Join a chat room"],
  missing: ["当前标签页没有有效邀请。请重新打开邀请链接。", "No valid invitation is available in this tab. Open the invitation link again."],
  storage: ["浏览器未能保存邀请。请允许标签页临时存储后重新打开链接。", "Your browser could not save the invitation. Allow session storage and open the link again."],
  unavailable: ["暂时无法确认主站登录，请重试。", "We could not confirm your sign-in. Please try again."],
  handoff: ["未能打开酒馆。请重试，或重新打开邀请链接。", "Tavern did not open. Try again or reopen your invitation link."],
} as const;

const router = useRouter();
const error = ref<"missing" | "storage" | "unavailable" | "handoff">();
const english = computed(() => currentLocale.value === "en-US");
const label = computed(() => TEXT.loading[english.value ? 1 : 0]);
const canRetry = computed(() => error.value === "unavailable" || error.value === "handoff");
let active: AbortController | undefined;
let navigationTimer: number | undefined;
let handedOffFlow: string | null = null;

/** 先接续既有主站认证，再以 /auth/me 复核精确主体；账号切换中不向酒馆转交。 */
async function currentMainSubject(signal: AbortSignal): Promise<string | null> {
  const session = UNIFIED_AUTH_ENABLED ? await ensurePrimarySession() : null;
  if (UNIFIED_AUTH_ENABLED ? !session : !hasAccessToken() && !getRefreshToken()) return null;
  try {
    const user = await apiGet<{ id?: unknown }>("/auth/me", { signal, cache: "no-store" });
    const subject = user?.id;
    // 主站 ID 是十进制字符串，与 OIDC sub 一致；不能转成 JS Number 丢失精度。
    if (typeof subject !== "string" || !/^[1-9][0-9]{0,31}$/.test(subject)
      || (session && session.subject !== subject)) throw new Error("tavern_main_subject_unconfirmed");
    return subject;
  } catch (failure) {
    if (isAuthenticationError(failure)) return null;
    throw failure;
  }
}

/** 主站只交接无入场权的流程标记及真实主体，不读取或发送酒馆邀请凭据。 */
async function continueInvite(): Promise<void> {
  active?.abort();
  window.clearTimeout(navigationTimer);
  const current = new AbortController();
  active = current;
  error.value = undefined;
  let flow: string | null;
  try {
    flow = handedOffFlow ?? loadTavernInviteFlow();
  } catch {
    error.value = "storage";
    return;
  }
  if (!flow) {
    error.value = "missing";
    return;
  }

  const checkTimer = window.setTimeout(() => {
    if (!current.signal.aborted) {
      error.value = "unavailable";
      current.abort();
    }
  }, 15_000);
  let subject: string | null;
  try {
    subject = await currentMainSubject(current.signal);
    if (current.signal.aborted) return;
  } catch {
    if (!current.signal.aborted) error.value = "unavailable";
    return;
  } finally {
    window.clearTimeout(checkTimer);
  }

  try {
    if (!subject && handedOffFlow) {
      restoreTavernInviteFlow(handedOffFlow);
      handedOffFlow = null;
    }
    if (subject && !handedOffFlow) clearTavernInviteFlow();
  } catch {
    error.value = "storage";
    return;
  }
  if (!subject) {
    // 邮件验证、二次验证和注册沿用已有账号流程；回跳不带流程标记，失败保留标签内的标记。
    try {
      const failure = await router.replace({ name: "auth", query: { redirect: TAVERN_INVITE_PATH } });
      if (failure && !current.signal.aborted) error.value = "unavailable";
    } catch {
      if (!current.signal.aborted) error.value = "unavailable";
    }
    return;
  }
  // 浏览器未完成离页时仅在本页内存保留一次接续；不再写回浏览器存储。
  handedOffFlow = flow;
  try {
    navigationTimer = window.setTimeout(() => { error.value = "handoff"; }, 10_000);
    window.location.replace(`https://tavern.pingxingxian.space/#/tavern-invite-return/${flow}/${subject}`);
  } catch {
    window.clearTimeout(navigationTimer);
    error.value = "handoff";
  }
}

onMounted(() => { void continueInvite(); });
watch(tavernInviteCaptureVersion, () => {
  handedOffFlow = null;
  void continueInvite();
});
onBeforeUnmount(() => {
  active?.abort();
  window.clearTimeout(navigationTimer);
});
</script>

<template>
  <ChatEntryLoading v-if="!error" :label="label" />
  <main v-else class="tavern-invite">
    <LanguageSwitcher class="tavern-invite__language" />
    <section class="tavern-invite__message" aria-labelledby="tavern-invite-heading">
      <h1 id="tavern-invite-heading">{{ TEXT.heading[english ? 1 : 0] }}</h1>
      <p role="alert">{{ TEXT[error][english ? 1 : 0] }}</p>
      <UiButton v-if="canRetry" tone="primary" @click="continueInvite">{{ uiText("重试") }}</UiButton>
      <RouterLink to="/games">{{ uiText("返回游戏") }}</RouterLink>
    </section>
  </main>
</template>

<style scoped>
.tavern-invite {
  display: grid;
  min-height: 100svh;
  place-items: center;
  padding: 1.5rem;
  background: var(--bg-app);
  color: var(--text);
}

.tavern-invite__message {
  display: grid;
  max-width: 28rem;
  justify-items: center;
  gap: .75rem;
  text-align: center;
}

.tavern-invite__message h1, .tavern-invite__message p {
  margin: 0;
}

.tavern-invite__language {
  position: fixed;
  z-index: 40;
  top: 12px;
  right: 16px;
}
</style>
