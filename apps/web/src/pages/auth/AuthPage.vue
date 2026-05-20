<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import {
  useConfirmPasswordReset,
  useLogin,
  useRegister,
  useRequestPasswordReset,
  useResendVerification,
  useVerifyTwoFactorLogin,
  useVerifyEmail,
} from "@/features/auth/queries";
import { ApiError } from "@/shared/api/client";
import UiBadge from "@/shared/ui/Badge.vue";
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";

type AuthTab = "login" | "register" | "forgot";

const USERNAME_PATTERN = /^[\p{L}\p{N}_.-]+$/u;
const USERNAME_HELPER = "用户名需为 3-32 位，可使用中文、字母、数字、点、下划线或短横线。";

const route = useRoute();
const router = useRouter();
const loginMutation = useLogin();
const verifyTwoFactorMutation = useVerifyTwoFactorLogin();
const registerMutation = useRegister();
const verifyEmailMutation = useVerifyEmail();
const resendVerificationMutation = useResendVerification();
const requestPasswordResetMutation = useRequestPasswordReset();
const confirmPasswordResetMutation = useConfirmPasswordReset();

const activeTab = ref<AuthTab>(readAuthTab(route.query.mode));
const account = ref("");
const loginPassword = ref("");
const twoFactorChallengeToken = ref("");
const twoFactorCode = ref("");
const username = ref("");
const email = ref("");
const registerPassword = ref("");
const resetEmail = ref("");
const resetToken = ref("");
const resetNewPassword = ref("");
const resetRequestedEmail = ref("");
const pendingVerificationEmail = ref("");
const verificationCode = ref("");
const devVerificationCode = ref<string | null>(null);
const formError = ref("");
const formNotice = ref("");

const isSubmitting = computed(
  () =>
    loginMutation.isPending.value ||
    verifyTwoFactorMutation.isPending.value ||
    registerMutation.isPending.value ||
    verifyEmailMutation.isPending.value ||
    resendVerificationMutation.isPending.value ||
    requestPasswordResetMutation.isPending.value ||
    confirmPasswordResetMutation.isPending.value,
);
const isVerifying = computed(() => verifyEmailMutation.isPending.value);
const isResending = computed(() => resendVerificationMutation.isPending.value);
const redirectTarget = computed(() => {
  const redirect = route.query.redirect;
  return typeof redirect === "string" && redirect.startsWith("/") ? redirect : "/";
});

watch(
  () => route.query.mode,
  (mode) => {
    activeTab.value = readAuthTab(mode);
    formError.value = "";
    formNotice.value = "";
  },
);

async function submitLogin() {
  formError.value = "";
  if (!account.value.trim() || !loginPassword.value) {
    formError.value = "请输入用户名/邮箱和密码。";
    return;
  }

  try {
    const response = await loginMutation.mutateAsync({
      account: account.value.trim(),
      password: loginPassword.value,
    });
    if (response.two_factor_required && response.challenge_token) {
      twoFactorChallengeToken.value = response.challenge_token;
      twoFactorCode.value = "";
      formNotice.value = "该账号已启用二次验证，请输入认证器或恢复码。";
      return;
    }

    await router.push(redirectTarget.value);
  } catch (error) {
    formError.value = toAuthError(error, "登录失败，请检查账号和密码。");
  }
}

async function submitTwoFactorLogin() {
  formError.value = "";
  const code = twoFactorCode.value.trim();
  if (code.length < 6) {
    formError.value = "请输入二次验证码或恢复码。";
    return;
  }

  try {
    await verifyTwoFactorMutation.mutateAsync({
      challenge_token: twoFactorChallengeToken.value,
      code,
    });
    await router.push(redirectTarget.value);
  } catch (error) {
    formError.value = toAuthError(error, "二次验证失败，请确认后重试。");
  }
}

async function requestPasswordReset() {
  formError.value = "";
  formNotice.value = "";
  const trimmedEmail = resetEmail.value.trim();
  if (!trimmedEmail) {
    formError.value = "请输入注册邮箱。";
    return;
  }

  try {
    const response = await requestPasswordResetMutation.mutateAsync({ email: trimmedEmail });
    resetRequestedEmail.value = trimmedEmail;
    formNotice.value = `如果邮箱存在，重置令牌已发送，请在 ${
      Math.floor(response.expires_in_seconds / 60)
    } 分钟内完成。`;
  } catch (error) {
    formError.value = toAuthError(error, "密码重置邮件暂时无法发送，请稍后再试。");
  }
}

async function confirmPasswordReset() {
  formError.value = "";
  formNotice.value = "";
  if (!resetToken.value.trim()) {
    formError.value = "请输入邮件中的重置令牌。";
    return;
  }

  if (resetNewPassword.value.length < 8) {
    formError.value = "新密码需至少 8 位。";
    return;
  }

  try {
    await confirmPasswordResetMutation.mutateAsync({
      token: resetToken.value.trim(),
      new_password: resetNewPassword.value,
    });
    resetToken.value = "";
    resetNewPassword.value = "";
    formNotice.value = "密码已重置，请使用新密码登录。";
    activeTab.value = "login";
    const query = { ...route.query };
    delete query.mode;
    await router.replace({ query });
  } catch (error) {
    formError.value = toAuthError(error, "重置失败，请确认令牌是否正确。");
  }
}

async function submitRegister() {
  formError.value = "";
  const trimmedUsername = username.value.trim();
  const trimmedEmail = email.value.trim();

  if (!isValidUsername(trimmedUsername)) {
    formError.value = USERNAME_HELPER;
    return;
  }

  if (!trimmedEmail) {
    formError.value = "请输入有效邮箱。";
    return;
  }

  if (registerPassword.value.length < 8) {
    formError.value = "请使用至少 8 位密码。";
    return;
  }

  try {
    const registration = await registerMutation.mutateAsync({
      username: trimmedUsername,
      email: trimmedEmail,
      password: registerPassword.value,
    });
    pendingVerificationEmail.value = registration.email;
    verificationCode.value = registration.dev_verification_code ?? "";
    devVerificationCode.value = registration.dev_verification_code;
    registerPassword.value = "";
    formNotice.value = `验证码已发送至 ${registration.email}，请在 ${
      Math.floor(registration.expires_in_seconds / 60)
    } 分钟内完成激活。`;
  } catch (error) {
    formError.value = toAuthError(error, "注册失败，请换一个用户名/邮箱后重试。");
  }
}

async function submitVerification() {
  formError.value = "";
  formNotice.value = "";
  const code = verificationCode.value.trim();
  if (!/^\d{6}$/.test(code)) {
    formError.value = "请输入 6 位数字验证码。";
    return;
  }

  try {
    await verifyEmailMutation.mutateAsync({
      email: pendingVerificationEmail.value,
      code,
    });
    await router.push(redirectTarget.value);
  } catch (error) {
    formError.value = toAuthError(error, "验证码校验失败，请确认后重试。");
  }
}

async function resendCode() {
  formError.value = "";
  formNotice.value = "";
  try {
    const registration = await resendVerificationMutation.mutateAsync({
      email: pendingVerificationEmail.value,
    });
    verificationCode.value = registration.dev_verification_code ?? "";
    devVerificationCode.value = registration.dev_verification_code;
    formNotice.value = `新的验证码已发送至 ${registration.email}。`;
  } catch (error) {
    formError.value = toAuthError(error, "验证码暂时无法重发，请稍后再试。");
  }
}

function resetPendingVerification() {
  pendingVerificationEmail.value = "";
  verificationCode.value = "";
  devVerificationCode.value = null;
  formError.value = "";
  formNotice.value = "";
}

function switchTab(tab: AuthTab) {
  activeTab.value = tab;
  formError.value = "";
  formNotice.value = "";
  twoFactorChallengeToken.value = "";
  twoFactorCode.value = "";
  if (tab === "login") {
    resetPendingVerification();
  }
  const query = { ...route.query };
  if (tab === "register" || tab === "forgot") {
    query.mode = tab;
  } else {
    delete query.mode;
  }

  void router.replace({ query });
}

function readAuthTab(mode: unknown): AuthTab {
  return mode === "register" || mode === "forgot" ? mode : "login";
}

function isValidUsername(value: string): boolean {
  return value.length >= 3 && value.length <= 32 && USERNAME_PATTERN.test(value);
}

function toAuthError(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    if (error.code === "account_exists") {
      return "用户名或邮箱已被注册。";
    }

    if (error.code === "invalid_credentials") {
      return "账号或密码不正确。";
    }

    if (error.code === "account_disabled") {
      return "账号当前不可用。";
    }

    if (error.code === "email_not_verified") {
      return "该邮箱尚未完成验证码激活，请先完成注册验证。";
    }

    if (error.code === "invalid_verification_code") {
      return "验证码不正确，请重新输入。";
    }

    if (error.code === "invalid_two_factor_code") {
      return "二次验证码或恢复码不正确。";
    }

    if (error.code === "invalid_reset_token") {
      return "密码重置令牌无效或已过期。";
    }

    if (error.code === "verification_code_expired") {
      return "验证码已过期，请重新发送。";
    }

    if (error.code === "verification_resend_limited") {
      return "验证码刚刚发送过，请稍后再试。";
    }

    if (error.code === "verification_attempts_exceeded") {
      return "验证码尝试次数过多，请重新发送验证码。";
    }

    if (error.code === "email_delivery_failed" || error.code === "email_delivery_unavailable") {
      return "验证码邮件暂时无法发送，请稍后再试。";
    }

    if (error.code === "validation_error") {
      return toValidationError(error.details) ?? fallback;
    }
  }

  return error instanceof Error && error.message ? error.message : fallback;
}

function toValidationError(details: Record<string, unknown>): string | null {
  const errors = details.errors;
  if (!Array.isArray(errors)) {
    return null;
  }

  if (hasFieldError(errors, "username")) {
    return USERNAME_HELPER;
  }

  if (hasFieldError(errors, "email")) {
    return "请输入有效邮箱。";
  }

  if (hasFieldError(errors, "password")) {
    return "密码需为 8-128 位。";
  }

  if (hasFieldError(errors, "new_password")) {
    return "新密码需为 8-128 位。";
  }

  if (hasFieldError(errors, "code")) {
    return "请输入 6 位数字验证码。";
  }

  if (hasFieldError(errors, "token")) {
    return "令牌格式不正确。";
  }

  return null;
}

function hasFieldError(errors: unknown[], field: string): boolean {
  return errors.some((error) => {
    if (!isRecord(error)) {
      return false;
    }

    const loc = error.loc;
    return Array.isArray(loc) && loc.some((part) => part === field);
  });
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
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
        <button type="button" :class="{ active: activeTab === 'forgot' }" @click="switchTab('forgot')">
          找回密码
        </button>
      </div>

      <form
        v-if="activeTab === 'login' && twoFactorChallengeToken"
        class="auth-form"
        aria-label="二次验证表单"
        @submit.prevent="submitTwoFactorLogin"
      >
        <p v-if="formNotice" class="auth-success" role="status">{{ formNotice }}</p>
        <label>
          <span>二次验证码或恢复码</span>
          <input
            v-model="twoFactorCode"
            autocomplete="one-time-code"
            placeholder="认证器 6 位验证码或恢复码"
          />
        </label>
        <p v-if="formError" class="auth-error" role="alert">{{ formError }}</p>
        <div class="auth-actions">
          <UiButton type="submit" tone="primary" :disabled="isSubmitting">
            {{ isSubmitting ? "验证中…" : "完成登录" }}
          </UiButton>
          <UiButton type="button" tone="subtle" :disabled="isSubmitting" @click="twoFactorChallengeToken = ''">
            返回登录
          </UiButton>
        </div>
      </form>

      <form
        v-else-if="activeTab === 'login'"
        class="auth-form"
        aria-label="登录表单"
        @submit.prevent="submitLogin"
      >
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
        <button type="button" class="auth-link-button" @click="switchTab('forgot')">忘记密码？</button>
      </form>

      <form v-else-if="activeTab === 'forgot'" class="auth-form" aria-label="找回密码表单">
        <p v-if="formNotice" class="auth-success" role="status">{{ formNotice }}</p>
        <label>
          <span>注册邮箱</span>
          <input v-model="resetEmail" type="email" autocomplete="email" placeholder="you@example.com" />
        </label>
        <UiButton type="button" tone="primary" :disabled="isSubmitting" @click="requestPasswordReset">
          {{ requestPasswordResetMutation.isPending.value ? "发送中…" : "发送重置令牌" }}
        </UiButton>
        <label>
          <span>重置令牌</span>
          <input v-model="resetToken" autocomplete="one-time-code" placeholder="粘贴邮件中的令牌" />
        </label>
        <label>
          <span>新密码</span>
          <input v-model="resetNewPassword" type="password" autocomplete="new-password" placeholder="至少 8 位" />
        </label>
        <p v-if="resetRequestedEmail" class="auth-helper">
          已为 <strong>{{ resetRequestedEmail }}</strong> 发起找回流程。为避免泄露账号状态，不会提示邮箱是否存在。
        </p>
        <p v-if="formError" class="auth-error" role="alert">{{ formError }}</p>
        <div class="auth-actions">
          <UiButton type="button" tone="primary" :disabled="isSubmitting" @click="confirmPasswordReset">
            {{ confirmPasswordResetMutation.isPending.value ? "重置中…" : "确认重置" }}
          </UiButton>
          <UiButton type="button" tone="subtle" :disabled="isSubmitting" @click="switchTab('login')">
            返回登录
          </UiButton>
        </div>
      </form>

      <form
        v-else-if="!pendingVerificationEmail"
        class="auth-form"
        aria-label="注册表单"
        @submit.prevent="submitRegister"
      >
        <label>
          <span>用户名</span>
          <input v-model="username" autocomplete="username" placeholder="3-32 位中文、字母、数字、点、下划线或短横线" />
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

      <form v-else class="auth-form" aria-label="验证码激活表单" @submit.prevent="submitVerification">
        <p v-if="formNotice" class="auth-success" role="status">{{ formNotice }}</p>
        <label>
          <span>邮箱验证码</span>
          <input
            v-model="verificationCode"
            autocomplete="one-time-code"
            inputmode="numeric"
            maxlength="6"
            placeholder="请输入 6 位验证码"
          />
        </label>
        <p v-if="devVerificationCode" class="auth-helper">
          本地开发验证码：<strong>{{ devVerificationCode }}</strong>
        </p>
        <p v-if="formError" class="auth-error" role="alert">{{ formError }}</p>
        <div class="auth-actions">
          <UiButton type="submit" tone="primary" :disabled="isSubmitting">
            {{ isVerifying ? "激活中…" : "激活账号" }}
          </UiButton>
          <UiButton type="button" tone="subtle" :disabled="isSubmitting" @click="resendCode">
            {{ isResending ? "发送中…" : "重新发送验证码" }}
          </UiButton>
        </div>
        <button type="button" class="auth-link-button" @click="resetPendingVerification">重新填写注册信息</button>
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
