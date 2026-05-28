<script setup lang="ts">
import { computed, ref } from "vue";

import {
  useChangePassword,
  useConfirmEmailChange,
  useCurrentUser,
  useOAuthProviders,
  useRegenerateRecoveryCodes,
  useRequestEmailChange,
  useRevokeOtherSessions,
  useRevokeSession,
  useSessions,
  useTwoFactorDisable,
  useTwoFactorEnable,
  useTwoFactorSetup,
} from "@/features/auth/queries";
import type { SessionResponse } from "@/features/auth/model";
import { ApiError } from "@/shared/api/client";
import UiBadge from "@/shared/ui/Badge.vue";
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";
import PasswordField from "@/shared/ui/PasswordField.vue";

const currentUserQuery = useCurrentUser();
const sessionsQuery = useSessions();
const oauthProvidersQuery = useOAuthProviders();
const changePasswordMutation = useChangePassword();
const requestEmailChangeMutation = useRequestEmailChange();
const confirmEmailChangeMutation = useConfirmEmailChange();
const setupTwoFactorMutation = useTwoFactorSetup();
const enableTwoFactorMutation = useTwoFactorEnable();
const disableTwoFactorMutation = useTwoFactorDisable();
const regenerateRecoveryCodesMutation = useRegenerateRecoveryCodes();
const revokeSessionMutation = useRevokeSession();
const revokeOtherSessionsMutation = useRevokeOtherSessions();

const currentPassword = ref("");
const newPassword = ref("");
const confirmNewPassword = ref("");
const passwordNotice = ref("");
const passwordError = ref("");

const newEmail = ref("");
const emailPassword = ref("");
const emailToken = ref("");
const emailNotice = ref("");
const emailError = ref("");

const twoFactorPassword = ref("");
const twoFactorCode = ref("");
const twoFactorSecret = ref("");
const twoFactorOtpAuthUrl = ref("");
const twoFactorNotice = ref("");
const twoFactorError = ref("");
const recoveryCodes = ref<string[]>([]);

const sessionNotice = ref("");
const sessionError = ref("");

const currentUser = computed(() => currentUserQuery.data.value);
const sessions = computed(() => sessionsQuery.data.value ?? []);
const oauthProviders = computed(() => oauthProvidersQuery.data.value?.providers ?? []);
const twoFactorEnabled = computed(() => Boolean(currentUser.value?.two_factor_enabled));
const sessionCount = computed(() => sessions.value.length);
const currentSession = computed(() => sessions.value.find((session) => session.current));
const securityStatus = computed(() =>
  twoFactorEnabled.value
    ? { label: "已加固", helper: "二次验证已开启", tone: "green" as const }
    : { label: "建议处理", helper: "建议开启二次验证", tone: "amber" as const },
);
const isSecurityBusy = computed(
  () =>
    changePasswordMutation.isPending.value ||
    requestEmailChangeMutation.isPending.value ||
    confirmEmailChangeMutation.isPending.value ||
    setupTwoFactorMutation.isPending.value ||
    enableTwoFactorMutation.isPending.value ||
    disableTwoFactorMutation.isPending.value ||
    regenerateRecoveryCodesMutation.isPending.value,
);

async function submitPasswordChange() {
  passwordError.value = "";
  passwordNotice.value = "";
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
    passwordNotice.value = "密码已更新，其他登录会话已自动撤销。";
  } catch (error) {
    passwordError.value = toSecurityError(error, "密码修改失败，请稍后再试。");
  }
}

async function requestEmailChange() {
  emailError.value = "";
  emailNotice.value = "";
  if (!newEmail.value.trim() || !emailPassword.value) {
    emailError.value = "请输入新邮箱和当前密码。";
    return;
  }

  try {
    const response = await requestEmailChangeMutation.mutateAsync({
      new_email: newEmail.value.trim(),
      password: emailPassword.value,
    });
    emailNotice.value = `确认令牌已发送至 ${response.email}，请在 ${
      Math.floor(response.expires_in_seconds / 60)
    } 分钟内完成。`;
    emailPassword.value = "";
  } catch (error) {
    emailError.value = toSecurityError(error, "邮箱变更请求失败，请稍后再试。");
  }
}

async function confirmEmailChange() {
  emailError.value = "";
  emailNotice.value = "";
  if (!emailToken.value.trim()) {
    emailError.value = "请输入邮箱确认令牌。";
    return;
  }

  try {
    const user = await confirmEmailChangeMutation.mutateAsync({ token: emailToken.value.trim() });
    emailToken.value = "";
    newEmail.value = "";
    emailNotice.value = `邮箱已更新为 ${user.email}。`;
  } catch (error) {
    emailError.value = toSecurityError(error, "邮箱确认失败，请检查令牌。");
  }
}

async function setupTwoFactor() {
  twoFactorError.value = "";
  twoFactorNotice.value = "";
  recoveryCodes.value = [];
  if (!twoFactorPassword.value) {
    twoFactorError.value = "请输入当前密码后再生成密钥。";
    return;
  }

  try {
    const response = await setupTwoFactorMutation.mutateAsync({
      password: twoFactorPassword.value,
    });
    twoFactorSecret.value = response.secret;
    twoFactorOtpAuthUrl.value = response.otpauth_url;
    twoFactorNotice.value = "密钥已生成，请添加到认证器后输入 6 位验证码启用。";
  } catch (error) {
    twoFactorError.value = toSecurityError(error, "二次验证初始化失败。");
  }
}

async function enableTwoFactor() {
  twoFactorError.value = "";
  twoFactorNotice.value = "";
  if (!twoFactorSecret.value || !twoFactorCode.value.trim()) {
    twoFactorError.value = "请先生成密钥，并输入认证器验证码。";
    return;
  }

  try {
    const response = await enableTwoFactorMutation.mutateAsync({
      secret: twoFactorSecret.value,
      code: twoFactorCode.value.trim(),
    });
    recoveryCodes.value = response.recovery_codes;
    twoFactorCode.value = "";
    twoFactorPassword.value = "";
    twoFactorNotice.value = "二次验证已启用，请立即保存恢复码。";
  } catch (error) {
    twoFactorError.value = toSecurityError(error, "二次验证启用失败。");
  }
}

async function disableTwoFactor() {
  twoFactorError.value = "";
  twoFactorNotice.value = "";
  if (!twoFactorPassword.value || !twoFactorCode.value.trim()) {
    twoFactorError.value = "请输入当前密码和二次验证码/恢复码。";
    return;
  }

  try {
    await disableTwoFactorMutation.mutateAsync({
      password: twoFactorPassword.value,
      code: twoFactorCode.value.trim(),
    });
    twoFactorPassword.value = "";
    twoFactorCode.value = "";
    recoveryCodes.value = [];
    twoFactorNotice.value = "二次验证已关闭。";
  } catch (error) {
    twoFactorError.value = toSecurityError(error, "二次验证关闭失败。");
  }
}

async function regenerateRecoveryCodes() {
  twoFactorError.value = "";
  twoFactorNotice.value = "";
  if (!twoFactorPassword.value || !twoFactorCode.value.trim()) {
    twoFactorError.value = "请输入当前密码和二次验证码/恢复码。";
    return;
  }

  try {
    const response = await regenerateRecoveryCodesMutation.mutateAsync({
      password: twoFactorPassword.value,
      code: twoFactorCode.value.trim(),
    });
    recoveryCodes.value = response.recovery_codes;
    twoFactorCode.value = "";
    twoFactorNotice.value = "新的恢复码已生成，旧恢复码已失效。";
  } catch (error) {
    twoFactorError.value = toSecurityError(error, "恢复码更新失败。");
  }
}

async function revokeSession(session: SessionResponse) {
  sessionError.value = "";
  sessionNotice.value = "";
  if (session.current) {
    sessionError.value = "当前会话请通过退出登录来结束。";
    return;
  }

  try {
    await revokeSessionMutation.mutateAsync(session.id);
    sessionNotice.value = "会话已撤销。";
  } catch (error) {
    sessionError.value = toSecurityError(error, "会话撤销失败。");
  }
}

async function revokeOthers() {
  sessionError.value = "";
  sessionNotice.value = "";
  try {
    const response = await revokeOtherSessionsMutation.mutateAsync();
    sessionNotice.value = `已撤销 ${response.revoked} 个其他会话。`;
  } catch (error) {
    sessionError.value = toSecurityError(error, "批量撤销失败。");
  }
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function toSecurityError(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    if (error.code === "invalid_credentials") {
      return "当前密码不正确。";
    }

    if (error.code === "invalid_two_factor_code") {
      return "二次验证码或恢复码不正确。";
    }

    if (error.code === "invalid_email_change_token") {
      return "邮箱确认令牌无效或已过期。";
    }

    if (error.code === "email_exists") {
      return "该邮箱已被其他账号使用。";
    }

    if (error.code === "session_not_found") {
      return "会话不存在或已撤销。";
    }

    if (error.code === "validation_error") {
      return "输入格式不正确，请检查后重试。";
    }
  }

  return error instanceof Error && error.message ? error.message : fallback;
}
</script>

<template>
  <section class="security-page">
    <header class="security-hero">
      <div class="security-hero__copy">
        <UiBadge tone="blue">安全中心</UiBadge>
        <h1>账号安全，一页处理。</h1>
        <p>修改密码、邮箱、二次验证和登录设备都在这里。</p>
      </div>
      <div v-if="currentUser" class="security-hero__status">
        <span>当前状态</span>
        <strong>{{ securityStatus.label }}</strong>
        <UiBadge :tone="securityStatus.tone">{{ securityStatus.helper }}</UiBadge>
      </div>
      <RouterLink v-if="!currentUser" class="security-login-link" :to="{ name: 'auth' }">先登录</RouterLink>
    </header>

    <div v-if="currentUser" class="security-overview" aria-label="账号安全概览">
      <UiCard class="overview-card">
        <span>账号</span>
        <strong>{{ currentUser.username }}</strong>
        <small>{{ currentUser.email }}</small>
      </UiCard>
      <UiCard class="overview-card">
        <span>二次验证</span>
        <strong>{{ twoFactorEnabled ? "已启用" : "未启用" }}</strong>
        <small>{{ twoFactorEnabled ? "登录时需要第二步验证" : "建议优先开启" }}</small>
      </UiCard>
      <UiCard class="overview-card">
        <span>登录设备</span>
        <strong>{{ sessionCount }}</strong>
        <small>{{ currentSession ? `当前设备 ${formatDate(currentSession.last_seen_at)}` : "暂无当前会话信息" }}</small>
      </UiCard>
    </div>

    <UiCard v-if="currentUser && !twoFactorEnabled" class="security-callout">
      <div>
        <UiBadge tone="amber">建议</UiBadge>
        <h2>开启二次验证，账号会更稳。</h2>
        <p>只需要认证器 App 的 6 位验证码；恢复码可以在手机丢失时找回账号。</p>
      </div>
      <a href="#two-factor-panel">去开启</a>
    </UiCard>

    <UiCard v-if="!currentUser" class="security-empty">
      <h2>需要登录后查看安全设置</h2>
      <p>登录后可修改密码、邮箱、启用 2FA，并管理活跃会话。</p>
      <RouterLink :to="{ name: 'auth', query: { redirect: '/security' } }">前往登录</RouterLink>
    </UiCard>

    <div v-if="currentUser" class="security-grid">
      <UiCard class="security-panel">
        <header>
          <h2>修改密码</h2>
          <p>更新后会保留当前设备，撤销其他会话。</p>
        </header>
        <form class="security-form" @submit.prevent="submitPasswordChange">
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
          <p v-if="passwordError" class="security-error">{{ passwordError }}</p>
          <p v-if="passwordNotice" class="security-success">{{ passwordNotice }}</p>
          <UiButton type="submit" tone="primary" :disabled="isSecurityBusy">保存密码</UiButton>
        </form>
      </UiCard>

      <UiCard class="security-panel">
        <header>
          <h2>修改邮箱</h2>
          <p>确认码会发送到新邮箱。</p>
        </header>
        <form class="security-form" @submit.prevent="requestEmailChange">
          <label>
            <span>新邮箱</span>
            <input v-model="newEmail" type="email" autocomplete="email" />
          </label>
          <label>
            <span>当前密码</span>
            <PasswordField v-model="emailPassword" autocomplete="current-password" />
          </label>
          <UiButton type="submit" tone="primary" :disabled="isSecurityBusy">发送确认令牌</UiButton>
        </form>
        <form class="security-form compact" @submit.prevent="confirmEmailChange">
          <label>
            <span>邮箱确认令牌</span>
            <input v-model="emailToken" autocomplete="one-time-code" />
          </label>
          <UiButton type="submit" tone="subtle" :disabled="isSecurityBusy">确认邮箱变更</UiButton>
        </form>
        <p v-if="emailError" class="security-error">{{ emailError }}</p>
        <p v-if="emailNotice" class="security-success">{{ emailNotice }}</p>
      </UiCard>

      <UiCard id="two-factor-panel" class="security-panel security-panel--wide security-panel--highlight">
        <header>
          <h2>二次验证</h2>
          <p>启用后登录需要认证器验证码或恢复码。</p>
        </header>
        <div v-if="!currentUser.two_factor_enabled" class="security-form">
          <label>
            <span>当前密码</span>
            <PasswordField v-model="twoFactorPassword" autocomplete="current-password" />
          </label>
          <UiButton tone="primary" :disabled="isSecurityBusy" @click="setupTwoFactor">生成认证器密钥</UiButton>
          <div v-if="twoFactorSecret" class="totp-secret">
            <span>密钥</span>
            <code>{{ twoFactorSecret }}</code>
            <small>{{ twoFactorOtpAuthUrl }}</small>
          </div>
          <label>
            <span>认证器验证码</span>
            <input v-model="twoFactorCode" autocomplete="one-time-code" />
          </label>
          <UiButton tone="subtle" :disabled="isSecurityBusy" @click="enableTwoFactor">启用二次验证</UiButton>
        </div>
        <div v-else class="security-form">
          <label>
            <span>当前密码</span>
            <PasswordField v-model="twoFactorPassword" autocomplete="current-password" />
          </label>
          <label>
            <span>验证码或恢复码</span>
            <input v-model="twoFactorCode" autocomplete="one-time-code" />
          </label>
          <div class="security-actions">
            <UiButton tone="subtle" :disabled="isSecurityBusy" @click="regenerateRecoveryCodes">换一组恢复码</UiButton>
            <UiButton tone="ghost" :disabled="isSecurityBusy" @click="disableTwoFactor">关闭二次验证</UiButton>
          </div>
        </div>
        <div v-if="recoveryCodes.length" class="recovery-grid" aria-label="恢复码">
          <code v-for="code in recoveryCodes" :key="code">{{ code }}</code>
        </div>
        <p v-if="twoFactorError" class="security-error">{{ twoFactorError }}</p>
        <p v-if="twoFactorNotice" class="security-success">{{ twoFactorNotice }}</p>
      </UiCard>

      <UiCard class="security-panel security-panel--wide">
        <header class="panel-header-row">
          <div>
            <h2>活跃会话</h2>
            <p>看到陌生设备就撤销。</p>
          </div>
          <UiButton tone="subtle" :disabled="revokeOtherSessionsMutation.isPending.value" @click="revokeOthers">
            撤销其他会话
          </UiButton>
        </header>
        <div v-if="sessionsQuery.isPending.value" class="session-empty">正在读取会话…</div>
        <div v-else-if="sessions.length === 0" class="session-empty">暂无活跃会话。</div>
        <ul v-else class="session-list">
          <li v-for="session in sessions" :key="session.id">
            <div>
              <strong>{{ session.user_agent || "未知设备" }}</strong>
              <span>{{ session.ip_address || "未知 IP" }} · {{ formatDate(session.last_seen_at) }}</span>
              <small v-if="session.current">当前会话</small>
            </div>
            <UiButton
              tone="ghost"
              :disabled="session.current || revokeSessionMutation.isPending.value"
              @click="revokeSession(session)"
            >
              撤销
            </UiButton>
          </li>
        </ul>
        <p v-if="sessionError" class="security-error">{{ sessionError }}</p>
        <p v-if="sessionNotice" class="security-success">{{ sessionNotice }}</p>
      </UiCard>

      <UiCard class="security-panel">
        <header>
          <h2>OAuth / SSO</h2>
          <p>外部登录提供方。</p>
        </header>
        <div v-if="oauthProviders.length" class="provider-list">
          <UiBadge v-for="provider in oauthProviders" :key="provider" tone="green">{{ provider }}</UiBadge>
        </div>
        <p v-else class="security-muted">暂未启用外部登录提供方。</p>
      </UiCard>
    </div>
  </section>
</template>

<style scoped lang="scss" src="./SecurityPage.scss"></style>
