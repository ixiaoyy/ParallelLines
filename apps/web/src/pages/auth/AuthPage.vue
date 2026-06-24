<script setup lang="ts">
import { computed, ref, watch, type Component } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  AppleFilled,
  CommentOutlined,
  DownOutlined,
  EditOutlined,
  EyeInvisibleOutlined,
  EyeOutlined,
  GithubFilled,
  GlobalOutlined,
  GoogleOutlined,
  LinkOutlined,
  LockOutlined,
  MailOutlined,
  SafetyOutlined,
  UserOutlined,
  WechatFilled,
} from "@ant-design/icons-vue";

import {
  useConfirmPasswordReset,
  useLogin,
  useOAuthProviders,
  useRegister,
  useRequestPasswordReset,
  useResendVerification,
  useVerifyTwoFactorLogin,
  useVerifyEmail,
} from "@/features/auth/queries";
import { ApiError } from "@/shared/api/client";
import { cssUrl, staticAssetUrl } from "@/shared/assets/staticAssets";
import UiButton from "@/shared/ui/Button.vue";

type AuthTab = "login" | "register" | "forgot";

interface OAuthProviderOption {
  id: string;
  label: string;
  icon: Component;
  tone: string;
}

const USERNAME_PATTERN = /^[\p{L}\p{N}_.-]+$/u;
const USERNAME_HELPER = "用户名需为 3-32 位，可使用中文、字母、数字、点、下划线或短横线。";
const shouldUseDevVerificationCode = import.meta.env.DEV;
const authMarkUrl = staticAssetUrl("/auth-visual/auth-mark.png");
const authPageStyle = computed(() => ({
  "--auth-pc-bg": cssUrl(staticAssetUrl("/auth-visual/parallel-auth-pc-bg.png")),
  "--auth-h5-bg": cssUrl(staticAssetUrl("/auth-visual/parallel-auth-h5-bg.png")),
}));

const OAUTH_PROVIDER_OPTIONS: Record<string, OAuthProviderOption> = {
  wechat: { id: "wechat", label: "微信", icon: WechatFilled, tone: "wechat" },
  github: { id: "github", label: "GitHub", icon: GithubFilled, tone: "github" },
  google: { id: "google", label: "Google", icon: GoogleOutlined, tone: "google" },
  apple: { id: "apple", label: "Apple", icon: AppleFilled, tone: "apple" },
};
const route = useRoute();
const router = useRouter();
const loginMutation = useLogin();
const oauthProvidersQuery = useOAuthProviders();
const verifyTwoFactorMutation = useVerifyTwoFactorLogin();
const registerMutation = useRegister();
const verifyEmailMutation = useVerifyEmail();
const resendVerificationMutation = useResendVerification();
const requestPasswordResetMutation = useRequestPasswordReset();
const confirmPasswordResetMutation = useConfirmPasswordReset();

const activeTab = ref<AuthTab>(readAuthTab(route.query.mode));
const account = ref("");
const loginPassword = ref("");
const rememberMe = ref(true);
const showLoginPassword = ref(false);
const twoFactorChallengeToken = ref("");
const twoFactorCode = ref("");
const showTwoFactorCode = ref(false);
const username = ref("");
const email = ref("");
const registerPassword = ref("");
const showRegisterPassword = ref(false);
const registerConfirmPassword = ref("");
const showConfirmPassword = ref(false);
const resetEmail = ref("");
const resetToken = ref("");
const resetNewPassword = ref("");
const showResetPassword = ref(false);
const resetConfirmPassword = ref("");
const showResetConfirmPassword = ref(false);
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
const availableOAuthProviders = computed(() =>
  (oauthProvidersQuery.data.value?.providers ?? []).flatMap((provider) => {
    const option = OAUTH_PROVIDER_OPTIONS[provider.toLowerCase()];
    return option ? [option] : [];
  }),
);

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
    await requestPasswordResetMutation.mutateAsync({ email: trimmedEmail });
    formNotice.value = "重置验证码已发送，请查收邮件。";
  } catch (error) {
    formError.value = toAuthError(error, "重置验证码发送失败，请稍后再试。");
  }
}

async function confirmPasswordReset() {
  formError.value = "";
  formNotice.value = "";
  const trimmedEmail = resetEmail.value.trim();
  const token = resetToken.value.trim();
  if (!trimmedEmail) {
    formError.value = "请输入注册邮箱。";
    return;
  }

  if (!/^\d{6}$/.test(token)) {
    formError.value = "请输入邮件中的 6 位重置验证码。";
    return;
  }

  if (resetNewPassword.value.length < 8) {
    formError.value = "新密码需至少 8 位。";
    return;
  }

  if (resetNewPassword.value !== resetConfirmPassword.value) {
    formError.value = "两次输入的新密码不一致。";
    return;
  }

  try {
    await confirmPasswordResetMutation.mutateAsync({
      email: trimmedEmail,
      token,
      new_password: resetNewPassword.value,
    });
    resetToken.value = "";
    resetNewPassword.value = "";
    resetConfirmPassword.value = "";
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

  if (registerPassword.value !== registerConfirmPassword.value) {
    formError.value = "两次输入的密码不一致。";
    return;
  }

  try {
    const registration = await registerMutation.mutateAsync({
      username: trimmedUsername,
      email: trimmedEmail,
      password: registerPassword.value,
    });
    pendingVerificationEmail.value = registration.email;
    verificationCode.value = shouldUseDevVerificationCode ? (registration.dev_verification_code ?? "") : "";
    devVerificationCode.value = shouldUseDevVerificationCode ? registration.dev_verification_code : null;
    registerPassword.value = "";
    registerConfirmPassword.value = "";
    formNotice.value = "验证码已发送，请查收邮件。";
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
    verificationCode.value = shouldUseDevVerificationCode ? (registration.dev_verification_code ?? "") : "";
    devVerificationCode.value = shouldUseDevVerificationCode ? registration.dev_verification_code : null;
    formNotice.value = "验证码已重新发送，请查收邮件。";
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

    if (error.code === "account_already_active") {
      return "该邮箱已完成验证，请直接登录。";
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
      return "重置验证码无效或已过期。";
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
    return "请输入邮件中的 6 位重置验证码。";
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
  <div class="auth-page" :class="`auth-page--${activeTab}`" :style="authPageStyle">
    <nav class="auth-topbar" aria-label="认证页导航">
      <RouterLink class="auth-topbar__brand" to="/" aria-label="返回首页">
        <img :src="authMarkUrl" alt="" class="auth-logo-mark" />
        <span>ParallelLines</span>
      </RouterLink>
      <div class="auth-topbar__actions">
        <button type="button" class="auth-language" aria-label="切换语言">
          <GlobalOutlined aria-hidden="true" />
          <span>简体中文</span>
          <DownOutlined aria-hidden="true" />
        </button>
        <RouterLink class="auth-official-link" to="/">访问官网</RouterLink>
      </div>
    </nav>

    <section class="auth-stage" aria-label="ParallelLines 登录注册">
      <aside class="auth-brand-panel">
        <div class="auth-brand-panel__lockup">
          <img :src="authMarkUrl" alt="" class="auth-brand-panel__mark" />
          <strong>ParallelLines</strong>
        </div>
        <h1>每一条平行线<br />都在这里相遇</h1>
        <p>ParallelLines, Infinite Possibilities</p>
        <ul class="auth-feature-list" aria-label="社区特性">
          <li>
            <span><EditOutlined aria-hidden="true" /></span>
            <strong>自由表达</strong>
            <small>分享观点，记录思考</small>
          </li>
          <li>
            <span><CommentOutlined aria-hidden="true" /></span>
            <strong>深度交流</strong>
            <small>遇见同好，碰撞思想</small>
          </li>
          <li>
            <span><LinkOutlined aria-hidden="true" /></span>
            <strong>连接世界</strong>
            <small>跨越边界，探索无限可能</small>
          </li>
        </ul>
      </aside>

      <main class="auth-panel" aria-label="账号认证">
        <div class="auth-card" :class="{ 'auth-card--dense': activeTab !== 'login' || twoFactorChallengeToken }">
          <div class="auth-card__brand">
            <img :src="authMarkUrl" alt="" class="auth-card__mark" />
            <strong>ParallelLines</strong>
            <span>连接思想，启发未来</span>
          </div>

          <div v-if="activeTab !== 'forgot'" class="auth-tabs" role="tablist" aria-label="认证方式">
            <button
              type="button"
              role="tab"
              :aria-selected="activeTab === 'login'"
              :class="{ active: activeTab === 'login' }"
              @click="switchTab('login')"
            >
              登录
            </button>
            <button
              type="button"
              role="tab"
              :aria-selected="activeTab === 'register'"
              :class="{ active: activeTab === 'register' }"
              @click="switchTab('register')"
            >
              注册
            </button>
          </div>
          <div v-else class="auth-recovery-heading">
            <strong>找回密码</strong>
            <button type="button" @click="switchTab('login')">返回登录</button>
          </div>

          <form
            v-if="activeTab === 'login' && twoFactorChallengeToken"
            class="auth-form"
            aria-label="二次验证表单"
            @submit.prevent="submitTwoFactorLogin"
          >
            <p v-if="formNotice" class="auth-success" role="status">{{ formNotice }}</p>
            <label class="auth-field">
              <span class="auth-field__label">二次验证码或恢复码</span>
              <span class="auth-field__control">
                <SafetyOutlined class="auth-field__icon" aria-hidden="true" />
                <input
                  v-model="twoFactorCode"
                  :type="showTwoFactorCode ? 'text' : 'password'"
                  autocomplete="one-time-code"
                  placeholder="验证码或恢复码"
                />
                <button
                  type="button"
                  class="auth-input-toggle"
                  :aria-label="showTwoFactorCode ? '隐藏验证码' : '显示验证码'"
                  @click="showTwoFactorCode = !showTwoFactorCode"
                >
                  <EyeOutlined v-if="showTwoFactorCode" />
                  <EyeInvisibleOutlined v-else />
                </button>
              </span>
            </label>
            <p v-if="formError" class="auth-error" role="alert">{{ formError }}</p>
            <div class="auth-actions">
              <UiButton class="auth-submit" type="submit" tone="primary" :disabled="isSubmitting">
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
            <p v-if="formNotice" class="auth-success" role="status">{{ formNotice }}</p>
            <label class="auth-field">
              <span class="auth-field__label">用户名 / 邮箱 / 手机号</span>
              <span class="auth-field__control">
                <UserOutlined class="auth-field__icon" aria-hidden="true" />
                <input v-model="account" type="text" autocomplete="username" placeholder="用户名 / 邮箱 / 手机号" />
              </span>
            </label>
            <label class="auth-field">
              <span class="auth-field__label">密码</span>
              <span class="auth-field__control">
                <LockOutlined class="auth-field__icon" aria-hidden="true" />
                <input
                  v-model="loginPassword"
                  :type="showLoginPassword ? 'text' : 'password'"
                  autocomplete="current-password"
                  placeholder="请输入密码"
                />
                <button
                  type="button"
                  class="auth-input-toggle"
                  :aria-label="showLoginPassword ? '隐藏密码' : '显示密码'"
                  @click="showLoginPassword = !showLoginPassword"
                >
                  <EyeOutlined v-if="showLoginPassword" />
                  <EyeInvisibleOutlined v-else />
                </button>
              </span>
            </label>
            <div class="auth-options">
              <label class="auth-check">
                <input v-model="rememberMe" type="checkbox" />
                <span aria-hidden="true"></span>
                记住我
              </label>
              <button type="button" class="auth-link-button" @click="switchTab('forgot')">忘记密码？</button>
            </div>
            <p v-if="formError" class="auth-error" role="alert">{{ formError }}</p>
            <UiButton class="auth-submit" type="submit" tone="primary" :disabled="isSubmitting">
              {{ isSubmitting ? "登录中…" : "登录" }}
            </UiButton>
            <div v-if="availableOAuthProviders.length" class="auth-social-block">
              <div class="auth-divider"><span>其他登录方式</span></div>
              <div class="auth-social-list" aria-label="其他登录方式">
                <button
                  v-for="provider in availableOAuthProviders"
                  :key="provider.id"
                  type="button"
                  class="auth-social"
                  :class="`auth-social--${provider.tone}`"
                  :aria-label="`${provider.label} 登录`"
                  @click="formNotice = `${provider.label} 登录入口尚未接入回调流程，请先使用账号密码登录。`"
                >
                  <component :is="provider.icon" aria-hidden="true" />
                  <span class="auth-social__label">{{ provider.label }}</span>
                </button>
              </div>
            </div>
            <p class="auth-switch-copy">还没有账号？ <button type="button" @click="switchTab('register')">立即注册</button></p>
          </form>

          <form v-else-if="activeTab === 'forgot'" class="auth-form auth-form--forgot" aria-label="找回密码表单">
            <p v-if="formNotice" class="auth-success" role="status">{{ formNotice }}</p>
            <label class="auth-field">
              <span class="auth-field__label">注册邮箱</span>
              <span class="auth-field__control">
                <MailOutlined class="auth-field__icon" aria-hidden="true" />
                <input v-model="resetEmail" type="email" autocomplete="email" placeholder="请输入注册邮箱" />
              </span>
            </label>
            <UiButton class="auth-submit" type="button" tone="primary" :disabled="isSubmitting" @click="requestPasswordReset">
              {{ requestPasswordResetMutation.isPending.value ? "发送中…" : "发送重置验证码" }}
            </UiButton>
            <label class="auth-field">
              <span class="auth-field__label">重置验证码</span>
              <span class="auth-field__control">
                <SafetyOutlined class="auth-field__icon" aria-hidden="true" />
                <input
                  v-model="resetToken"
                  type="text"
                  autocomplete="one-time-code"
                  inputmode="numeric"
                  maxlength="6"
                  placeholder="6 位验证码"
                />
              </span>
            </label>
            <label class="auth-field">
              <span class="auth-field__label">新密码</span>
              <span class="auth-field__control">
                <LockOutlined class="auth-field__icon" aria-hidden="true" />
                <input
                  v-model="resetNewPassword"
                  :type="showResetPassword ? 'text' : 'password'"
                  autocomplete="new-password"
                  placeholder="至少 8 位"
                />
                <button
                  type="button"
                  class="auth-input-toggle"
                  :aria-label="showResetPassword ? '隐藏密码' : '显示密码'"
                  @click="showResetPassword = !showResetPassword"
                >
                  <EyeOutlined v-if="showResetPassword" />
                  <EyeInvisibleOutlined v-else />
                </button>
              </span>
            </label>
            <label class="auth-field">
              <span class="auth-field__label">确认新密码</span>
              <span class="auth-field__control">
                <LockOutlined class="auth-field__icon" aria-hidden="true" />
                <input
                  v-model="resetConfirmPassword"
                  :type="showResetConfirmPassword ? 'text' : 'password'"
                  autocomplete="new-password"
                  placeholder="再次输入新密码"
                />
                <button
                  type="button"
                  class="auth-input-toggle"
                  :aria-label="showResetConfirmPassword ? '隐藏密码' : '显示密码'"
                  @click="showResetConfirmPassword = !showResetConfirmPassword"
                >
                  <EyeOutlined v-if="showResetConfirmPassword" />
                  <EyeInvisibleOutlined v-else />
                </button>
              </span>
            </label>
            <p v-if="formError" class="auth-error" role="alert">{{ formError }}</p>
            <div class="auth-actions">
              <UiButton class="auth-submit" type="button" tone="primary" :disabled="isSubmitting" @click="confirmPasswordReset">
                {{ confirmPasswordResetMutation.isPending.value ? "重置中…" : "确认重置" }}
              </UiButton>
              <UiButton type="button" tone="subtle" :disabled="isSubmitting" @click="switchTab('login')">
                返回登录
              </UiButton>
            </div>
          </form>

          <form
            v-else-if="!pendingVerificationEmail"
            class="auth-form auth-form--register"
            aria-label="注册表单"
            @submit.prevent="submitRegister"
          >
            <label class="auth-field">
              <span class="auth-field__label">用户名</span>
              <span class="auth-field__control">
                <UserOutlined class="auth-field__icon" aria-hidden="true" />
                <input v-model="username" type="text" autocomplete="username" placeholder="用户名" />
              </span>
            </label>
            <label class="auth-field">
              <span class="auth-field__label">邮箱</span>
              <span class="auth-field__control">
                <MailOutlined class="auth-field__icon" aria-hidden="true" />
                <input v-model="email" type="email" autocomplete="email" placeholder="邮箱" />
              </span>
            </label>
            <label class="auth-field">
              <span class="auth-field__label">密码</span>
              <span class="auth-field__control">
                <LockOutlined class="auth-field__icon" aria-hidden="true" />
                <input
                  v-model="registerPassword"
                  :type="showRegisterPassword ? 'text' : 'password'"
                  autocomplete="new-password"
                  placeholder="至少 8 位密码"
                />
                <button
                  type="button"
                  class="auth-input-toggle"
                  :aria-label="showRegisterPassword ? '隐藏密码' : '显示密码'"
                  @click="showRegisterPassword = !showRegisterPassword"
                >
                  <EyeOutlined v-if="showRegisterPassword" />
                  <EyeInvisibleOutlined v-else />
                </button>
              </span>
            </label>
            <label class="auth-field">
              <span class="auth-field__label">确认密码</span>
              <span class="auth-field__control">
                <LockOutlined class="auth-field__icon" aria-hidden="true" />
                <input
                  v-model="registerConfirmPassword"
                  :type="showConfirmPassword ? 'text' : 'password'"
                  autocomplete="new-password"
                  placeholder="再次输入密码"
                />
                <button
                  type="button"
                  class="auth-input-toggle"
                  :aria-label="showConfirmPassword ? '隐藏密码' : '显示密码'"
                  @click="showConfirmPassword = !showConfirmPassword"
                >
                  <EyeOutlined v-if="showConfirmPassword" />
                  <EyeInvisibleOutlined v-else />
                </button>
              </span>
            </label>
            <p v-if="formError" class="auth-error" role="alert">{{ formError }}</p>
            <UiButton class="auth-submit" type="submit" tone="primary" :disabled="isSubmitting">
              {{ isSubmitting ? "注册中…" : "注册" }}
            </UiButton>
            <p class="auth-switch-copy">已有账号？ <button type="button" @click="switchTab('login')">立即登录</button></p>
          </form>

          <form v-else class="auth-form" aria-label="验证码激活表单" @submit.prevent="submitVerification">
            <p v-if="formNotice" class="auth-success" role="status">{{ formNotice }}</p>
            <label class="auth-field">
              <span class="auth-field__label">邮箱验证码</span>
              <span class="auth-field__control">
                <SafetyOutlined class="auth-field__icon" aria-hidden="true" />
                <input
                  v-model="verificationCode"
                  type="text"
                  autocomplete="one-time-code"
                  inputmode="numeric"
                  maxlength="6"
                  placeholder="6 位验证码"
                />
              </span>
            </label>
            <p v-if="shouldUseDevVerificationCode && devVerificationCode" class="auth-helper">
              本地开发验证码：<strong>{{ devVerificationCode }}</strong>
            </p>
            <p v-if="formError" class="auth-error" role="alert">{{ formError }}</p>
            <div class="auth-actions">
              <UiButton class="auth-submit" type="submit" tone="primary" :disabled="isSubmitting">
                {{ isVerifying ? "激活中…" : "激活账号" }}
              </UiButton>
              <UiButton type="button" tone="subtle" :disabled="isSubmitting" @click="resendCode">
                {{ isResending ? "发送中…" : "重新发送验证码" }}
              </UiButton>
            </div>
            <button type="button" class="auth-link-button auth-link-button--center" @click="resetPendingVerification">
              重新填写注册信息
            </button>
          </form>
        </div>
      </main>
    </section>

    <footer class="auth-footer" aria-label="认证页页脚">
      <span>© 2024 ParallelLines. All rights reserved.</span>
      <RouterLink to="/">用户协议</RouterLink>
      <RouterLink to="/">隐私政策</RouterLink>
      <RouterLink to="/boards">社区规范</RouterLink>
      <RouterLink to="/">帮助中心</RouterLink>
    </footer>
  </div>
</template>

<style scoped lang="scss" src="./AuthPage.scss"></style>
