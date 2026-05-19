<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { useLogin, useRegister } from "@/features/auth/queries";
import UiBadge from "@/shared/ui/Badge.vue";
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";

type AuthTab = "login" | "register";

const route = useRoute();
const router = useRouter();
const loginMutation = useLogin();
const registerMutation = useRegister();

const activeTab = ref<AuthTab>(readAuthTab(route.query.mode));
const account = ref("");
const loginPassword = ref("");
const username = ref("");
const email = ref("");
const registerPassword = ref("");
const formError = ref("");

const isSubmitting = computed(() => loginMutation.isPending.value || registerMutation.isPending.value);
const redirectTarget = computed(() => {
  const redirect = route.query.redirect;
  return typeof redirect === "string" && redirect.startsWith("/") ? redirect : "/";
});

watch(
  () => route.query.mode,
  (mode) => {
    activeTab.value = readAuthTab(mode);
    formError.value = "";
  },
);

async function submitLogin() {
  formError.value = "";
  if (!account.value.trim() || !loginPassword.value) {
    formError.value = "请输入用户名/邮箱和密码。";
    return;
  }

  try {
    await loginMutation.mutateAsync({ account: account.value.trim(), password: loginPassword.value });
    await router.push(redirectTarget.value);
  } catch (error) {
    formError.value = toAuthError(error, "登录失败，请检查账号和密码。");
  }
}

async function submitRegister() {
  formError.value = "";
  if (!username.value.trim() || !email.value.trim() || registerPassword.value.length < 8) {
    formError.value = "请输入用户名、邮箱，并使用至少 8 位密码。";
    return;
  }

  try {
    await registerMutation.mutateAsync({
      username: username.value.trim(),
      email: email.value.trim(),
      password: registerPassword.value,
    });
    await router.push(redirectTarget.value);
  } catch (error) {
    formError.value = toAuthError(error, "注册失败，请换一个用户名/邮箱后重试。");
  }
}

function switchTab(tab: AuthTab) {
  activeTab.value = tab;
  formError.value = "";
  const query = { ...route.query };
  if (tab === "register") {
    query.mode = "register";
  } else {
    delete query.mode;
  }

  void router.replace({ query });
}

function readAuthTab(mode: unknown): AuthTab {
  return mode === "register" ? "register" : "login";
}

function toAuthError(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}
</script>

<template>
  <div class="auth-page">
    <UiCard class="auth-card">
      <header class="auth-heading">
        <UiBadge tone="blue">账户</UiBadge>
        <h1 id="auth-title">加入平行线，继续清晰讨论。</h1>
        <p>登录后可以发布主题、回复楼层、关注版块，并把有价值的结论收藏起来。</p>
      </header>

      <div class="auth-tabs" role="tablist" aria-label="认证方式">
        <button type="button" :class="{ active: activeTab === 'login' }" @click="switchTab('login')">登录</button>
        <button type="button" :class="{ active: activeTab === 'register' }" @click="switchTab('register')">注册</button>
      </div>

      <form v-if="activeTab === 'login'" class="auth-form" aria-label="登录表单" @submit.prevent="submitLogin">
        <label>
          <span>用户名或邮箱</span>
          <input v-model="account" autocomplete="username" placeholder="username 或 you@example.com" />
        </label>
        <label>
          <span>密码</span>
          <input v-model="loginPassword" type="password" autocomplete="current-password" placeholder="请输入密码" />
        </label>
        <p v-if="formError" class="auth-error" role="alert">{{ formError }}</p>
        <UiButton type="submit" tone="primary" :disabled="isSubmitting">
          {{ isSubmitting ? "登录中…" : "登录" }}
        </UiButton>
      </form>

      <form v-else class="auth-form" aria-label="注册表单" @submit.prevent="submitRegister">
        <label>
          <span>用户名</span>
          <input v-model="username" autocomplete="username" placeholder="3-32 位字母、数字、点、下划线或短横线" />
        </label>
        <label>
          <span>邮箱</span>
          <input v-model="email" type="email" autocomplete="email" placeholder="you@example.com" />
        </label>
        <label>
          <span>密码</span>
          <input v-model="registerPassword" type="password" autocomplete="new-password" placeholder="至少 8 位" />
        </label>
        <p v-if="formError" class="auth-error" role="alert">{{ formError }}</p>
        <UiButton type="submit" tone="primary" :disabled="isSubmitting">
          {{ isSubmitting ? "注册中…" : "创建账号" }}
        </UiButton>
      </form>
    </UiCard>

    <aside class="auth-notes" aria-label="账户能力">
      <h2>账户能做什么</h2>
      <ul class="auth-steps">
        <li>
          <strong>发主题</strong>
          <span>把问题放进合适版块</span>
        </li>
        <li>
          <strong>接楼层</strong>
          <span>追问、补充、复盘都留在同一条线</span>
        </li>
        <li>
          <strong>收结论</strong>
          <span>关注回复，把答案留给后来的人</span>
        </li>
      </ul>
    </aside>
  </div>
</template>

<style scoped lang="scss" src="./AuthPage.scss"></style>
