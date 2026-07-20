<script setup lang="ts">
import {
  CheckCircleOutlined,
  ClockCircleOutlined,
  KeyOutlined,
  LockOutlined,
  SearchOutlined,
  SafetyCertificateOutlined,
  StopOutlined,
  TeamOutlined,
} from "@ant-design/icons-vue";
import { message, Modal } from "ant-design-vue";
import { computed, onBeforeUnmount, reactive, ref, watch } from "vue";

import {
  adminRoleLabel,
  adminStatusLabel,
  type AdminFableSpaceAccessGrantResponse,
} from "@/features/admin/model";
import {
  useAdminFableSpaceAccessGrants,
  useRevokeAdminFableSpaceAccessGrant,
  useUpdateAdminFableSpaceAccessGrant,
} from "@/features/admin/queries";
import type { FableSpaceAccessLevel } from "@/features/auth/model";
import UiAvatar from "@/shared/ui/Avatar.vue";
import UiButton from "@/shared/ui/Button.vue";

interface AccessLevelOption {
  value: FableSpaceAccessLevel;
  label: string;
  eyebrow: string;
  description: string;
}

const accessLevelOptions: AccessLevelOption[] = [
  {
    value: "access",
    label: "基础体验",
    eyebrow: "Access",
    description: "所有正常登录用户已自动拥有；保留此级别仅用于兼容已有授权记录。",
  },
  {
    value: "creator",
    label: "创作者",
    eyebrow: "Creator",
    description: "包含体验权限，并可新建空间、Home、领地和寻宝路线。",
  },
  {
    value: "operator",
    label: "产品运营",
    eyebrow: "Operator",
    description: "包含创作者能力，为后续运营工具预留；当前不绕过任何空间主权。",
  },
  {
    value: "admin",
    label: "产品管理员",
    eyebrow: "Admin",
    description: "包含全部产品能力；授权仍由论坛管理员管理，也不绕过空间主权。",
  },
];

const searchInput = ref("");
const searchQuery = ref("");
const selectedUserId = ref("");
const grantDraft = reactive({
  accessLevel: "access" as FableSpaceAccessLevel,
  expiresAt: "",
});
let searchTimerId: number | undefined;

// Builds stable server search parameters from the debounced identity query.
// Parameters: none. Return value includes query and limit; side effect: none.
const grantParams = computed(() => ({
  query: searchQuery.value || undefined,
  limit: 50,
}));
const grantsQuery = useAdminFableSpaceAccessGrants(grantParams);
const updateGrantMutation = useUpdateAdminFableSpaceAccessGrant();
const revokeGrantMutation = useRevokeAdminFableSpaceAccessGrant();
const users = computed(() => grantsQuery.data.value ?? []);
// Counts current explicit grants within this search result; baseline access is intentionally excluded.
// Parameters: none. Return value is the visible configured-grant count; side effect: none.
const visibleGrantCount = computed(
  () =>
    users.value.filter(
      (user) =>
        Boolean(user.access_level) &&
        !user.revoked_at &&
        (!user.expires_at || new Date(user.expires_at).getTime() > Date.now()),
    ).length,
);
// Resolves the selected user against the latest query response so mutations never edit stale rows.
// Parameters: none. Return value is the current result row or null; side effect: none.
const selectedUser = computed(
  () => users.value.find((user) => user.user_id === selectedUserId.value) ?? null,
);
// Returns the product-level description shown beside the form selection.
// Parameters: none. Return value is the selected level metadata; side effect: none.
const selectedLevelOption = computed(
  () => accessLevelOptions.find((option) => option.value === grantDraft.accessLevel)!,
);
// Prevents overlapping grant and revoke writes for the same user.
// Parameters: none. Return value is true while either mutation is pending; side effect: none.
const mutationPending = computed(
  () => updateGrantMutation.isPending.value || revokeGrantMutation.isPending.value,
);
// Allows explicit grant writes only for active accounts accepted by the backend contract.
// Parameters: none. Return value is true when the selected account may receive a persisted grant; side effect: none.
const canEditSelectedGrant = computed(
  () => Boolean(selectedUser.value && selectedUser.value.account_status === "active"),
);

watch(
  searchInput,
  (value) => {
    window.clearTimeout(searchTimerId);
    searchTimerId = window.setTimeout(() => {
      searchQuery.value = value.trim();
    }, 300);
  },
);

watch(
  users,
  (nextUsers) => {
    if (!nextUsers.some((user) => user.user_id === selectedUserId.value)) {
      selectedUserId.value = nextUsers[0]?.user_id ?? "";
    }
  },
  { immediate: true },
);

watch(
  selectedUser,
  (user) => {
    grantDraft.accessLevel = user?.access_level ?? "access";
    grantDraft.expiresAt = toDateTimeLocal(user?.expires_at ?? null);
    updateGrantMutation.reset();
    revokeGrantMutation.reset();
  },
  { immediate: true },
);

onBeforeUnmount(() => window.clearTimeout(searchTimerId));

// Selects a result row for product-access editing.
// `user` is a combined forum identity and FableSpace grant row. Return value: none. Side effect: changes the active editor.
function selectUser(user: AdminFableSpaceAccessGrantResponse): void {
  selectedUserId.value = user.user_id;
}

// Saves a new or updated FableSpace grant after validating the optional local expiry.
// Parameters: none. Return value: none. Side effect: performs an admin PUT and shows mutation feedback.
function saveGrant(): void {
  const user = selectedUser.value;
  if (!user || mutationPending.value || !canEditSelectedGrant.value) {
    return;
  }

  const expiresAt = toIsoDateTime(grantDraft.expiresAt);
  if (grantDraft.expiresAt && !expiresAt) {
    message.warning("请输入有效的到期时间");
    return;
  }
  if (expiresAt && new Date(expiresAt).getTime() <= Date.now()) {
    message.warning("到期时间需要晚于当前时间");
    return;
  }

  updateGrantMutation.mutate(
    {
      userId: user.user_id,
      payload: {
        access_level: grantDraft.accessLevel,
        expires_at: expiresAt,
      },
    },
    {
      onSuccess: () => message.success(`已更新 ${user.username} 的 FableSpace 高级能力`),
    },
  );
}

// Confirms and revokes only the selected user's explicit FableSpace capability grant.
// Parameters: none. Return value: none. Side effect: opens a confirmation dialog and may perform an admin DELETE.
function confirmRevokeGrant(): void {
  const user = selectedUser.value;
  if (!user?.access_level || mutationPending.value) {
    return;
  }

  Modal.confirm({
    title: `撤销 ${user.username} 的 FableSpace 高级能力？`,
    content: "账号会回退到基础体验；论坛账号、角色、内容和基础入口不会改变。",
    okText: "确认撤销",
    okType: "danger",
    cancelText: "取消",
    centered: true,
    onOk: async () => {
      await revokeGrantMutation.mutateAsync(user.user_id);
      message.success(`已撤销 ${user.username} 的 FableSpace 高级能力`);
    },
  });
}

// Applies a common future expiry while retaining a precise editable datetime field.
// `days` is the number of full days from now. Return value: none. Side effect: updates the form draft.
function setExpiryDays(days: number): void {
  const expiry = new Date();
  expiry.setDate(expiry.getDate() + days);
  grantDraft.expiresAt = toDateTimeLocal(expiry.toISOString());
}

// Removes the expiry from the current draft so access remains valid until explicitly revoked.
// Parameters: none. Return value: none. Side effect: clears the expiry field.
function clearExpiry(): void {
  grantDraft.expiresAt = "";
}

// Converts an API ISO timestamp to the browser-local datetime input format.
// `iso` may be null for permanent access. Return value is YYYY-MM-DDTHH:mm or empty; side effect: none.
function toDateTimeLocal(iso: string | null): string {
  if (!iso) {
    return "";
  }
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  const offsetMs = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offsetMs).toISOString().slice(0, 16);
}

// Converts a browser-local datetime value to the API's ISO timestamp.
// `value` may be empty for no expiry. Return value is ISO or null when empty/invalid; side effect: none.
function toIsoDateTime(value: string): string | null {
  if (!value) {
    return null;
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

// Formats an API timestamp for compact audit and expiry display.
// `iso` may be null. Return value is localized date/time or the supplied fallback; side effect: none.
function formatDateTime(iso: string | null, fallback = "未记录"): string {
  if (!iso) {
    return fallback;
  }
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return fallback;
  }
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

// Maps one grant row to its operational status copy.
// `user` contains account and entitlement state. Return value is a short Chinese label; side effect: none.
function grantStatusLabel(user: AdminFableSpaceAccessGrantResponse): string {
  if (!user.access_level || user.revoked_at) {
    return user.account_status === "active" ? "基础访问" : "账号不可用";
  }
  if (
    user.account_status !== "active" ||
    (user.expires_at && new Date(user.expires_at).getTime() <= Date.now())
  ) {
    return "高级权限失效";
  }
  if (user.expires_at && new Date(user.expires_at).getTime() - Date.now() < 7 * 86_400_000) {
    return "高级权限将到期";
  }
  return "高级权限已配置";
}

// Maps one grant row to a semantic style suffix.
// `user` contains account and entitlement state. Return value is a CSS status key; side effect: none.
function grantStatusClass(user: AdminFableSpaceAccessGrantResponse): string {
  const label = grantStatusLabel(user);
  if (label === "高级权限已配置") return "active";
  if (label === "高级权限将到期") return "warning";
  if (label === "高级权限失效" || label === "账号不可用") return "expired";
  return "none";
}

// Converts an access-level enum into the product-facing label used in rows and summaries.
// `level` may be null for ungranted users. Return value is the localized level label; side effect: none.
function accessLevelLabel(level: FableSpaceAccessLevel | null): string {
  return accessLevelOptions.find((option) => option.value === level)?.label ?? "未分配";
}
</script>

<template>
  <section class="fablespace-access-panel" aria-labelledby="fablespace-access-title">
    <header class="fablespace-access-panel__header">
      <div>
        <span class="fablespace-access-panel__context">独立产品能力管理</span>
        <h1 id="fablespace-access-title">FableSpace 高级能力</h1>
        <p>所有正常登录用户均可进入；在这里管理创作、运营与产品管理能力。</p>
      </div>
      <div v-if="!grantsQuery.isLoading.value && !grantsQuery.isError.value" class="result-summary">
        <strong>{{ visibleGrantCount }}</strong>
        <span>位已配置 / 当前 {{ users.length }} 位</span>
      </div>
    </header>

    <aside class="product-boundary-note" aria-label="权限边界说明">
      <span class="product-boundary-note__icon"><LockOutlined aria-hidden="true" /></span>
      <div>
        <strong>基础访问已经向登录用户开放</strong>
        <p>这里的设置只影响 FableSpace 高级能力，不改变基础入口，也不改变论坛角色、等级、发帖权限或内容。</p>
      </div>
      <span class="product-boundary-note__tag">与论坛角色解耦</span>
    </aside>

    <div class="access-workspace">
      <aside class="access-directory" aria-label="用户高级能力列表">
        <label class="access-search">
          <span class="sr-only">搜索用户名或邮箱</span>
          <SearchOutlined aria-hidden="true" />
          <input v-model="searchInput" type="search" placeholder="搜索用户名或邮箱" autocomplete="off" />
          <kbd v-if="searchQuery">{{ users.length }}</kbd>
        </label>

        <header class="access-directory__heading">
          <div>
            <h2>账号目录</h2>
            <p>搜索结果包含仅有基础访问的账号</p>
          </div>
          <TeamOutlined aria-hidden="true" />
        </header>

        <div v-if="grantsQuery.isLoading.value" class="access-list-skeleton" role="status">
          <span class="sr-only">授权列表加载中…</span>
          <i v-for="index in 7" :key="index" />
        </div>
        <div v-else-if="grantsQuery.isError.value" class="access-state is-error" role="alert">
          <strong>账号目录加载失败</strong>
          <p>{{ grantsQuery.error.value?.message || "请检查网络或管理员权限后重试。" }}</p>
          <UiButton tone="subtle" :disabled="grantsQuery.isFetching.value" @click="grantsQuery.refetch()">
            {{ grantsQuery.isFetching.value ? "重试中…" : "重新加载" }}
          </UiButton>
        </div>
        <div v-else-if="users.length" class="access-list">
          <button
            v-for="user in users"
            :key="user.user_id"
            type="button"
            :class="{ 'is-active': user.user_id === selectedUserId }"
            :aria-pressed="user.user_id === selectedUserId"
            @click="selectUser(user)"
          >
            <UiAvatar :src="user.avatar_url" :name="user.username" :role="user.forum_role" size="sm" />
            <span class="access-list__identity">
              <strong>{{ user.username }}</strong>
              <small>{{ user.email }}</small>
            </span>
            <span class="access-list__status" :class="`is-${grantStatusClass(user)}`">
              {{ grantStatusLabel(user) }}
            </span>
          </button>
        </div>
        <div v-else class="access-state">
          <SearchOutlined aria-hidden="true" />
          <strong>没有匹配的账号</strong>
          <p>尝试输入完整用户名或邮箱。</p>
        </div>
      </aside>

      <article v-if="selectedUser" class="grant-editor">
        <header class="grant-editor__identity">
          <UiAvatar
            :src="selectedUser.avatar_url"
            :name="selectedUser.username"
            :role="selectedUser.forum_role"
            size="lg"
          />
          <div>
            <span>正在配置</span>
            <h2>{{ selectedUser.display_name || selectedUser.username }}</h2>
            <p>{{ selectedUser.email }}</p>
          </div>
          <span class="grant-status" :class="`is-${grantStatusClass(selectedUser)}`">
            {{ grantStatusLabel(selectedUser) }}
          </span>
        </header>

        <dl class="identity-boundary">
          <div>
            <dt>论坛角色</dt>
            <dd>{{ adminRoleLabel(selectedUser.forum_role) }}</dd>
          </div>
          <div>
            <dt>论坛状态</dt>
            <dd>{{ adminStatusLabel(selectedUser.account_status) }}</dd>
          </div>
          <div>
            <dt>当前产品级别</dt>
            <dd>{{ accessLevelLabel(selectedUser.access_level) }}</dd>
          </div>
          <div>
            <dt>有效期</dt>
            <dd>{{ formatDateTime(selectedUser.expires_at, "长期有效") }}</dd>
          </div>
        </dl>

        <section class="editor-section" aria-labelledby="access-level-title">
          <header class="editor-section__heading">
            <div>
              <span>01</span>
              <div>
                <h3 id="access-level-title">选择产品权限</h3>
                <p>高等级包含其下方等级的产品能力。</p>
              </div>
            </div>
            <KeyOutlined aria-hidden="true" />
          </header>

          <div class="access-level-grid">
            <label
              v-for="option in accessLevelOptions"
              :key="option.value"
              :class="{ 'is-selected': grantDraft.accessLevel === option.value }"
            >
              <input
                v-model="grantDraft.accessLevel"
                type="radio"
                :value="option.value"
                :disabled="!canEditSelectedGrant"
              />
              <span class="access-level-grid__index">{{ option.eyebrow }}</span>
              <strong>{{ option.label }}</strong>
              <p>{{ option.description }}</p>
              <CheckCircleOutlined aria-hidden="true" />
            </label>
          </div>

          <div class="selected-level-note">
            <SafetyCertificateOutlined aria-hidden="true" />
            <p><strong>{{ selectedLevelOption.label }}</strong>{{ selectedLevelOption.description }}</p>
          </div>
        </section>

        <section class="editor-section" aria-labelledby="access-expiry-title">
          <header class="editor-section__heading">
            <div>
              <span>02</span>
              <div>
                <h3 id="access-expiry-title">设置有效期</h3>
                <p>到期后高级能力自动失效，账号仍可继续基础体验。</p>
              </div>
            </div>
            <ClockCircleOutlined aria-hidden="true" />
          </header>

          <div class="expiry-editor">
            <label>
              <span>到期时间</span>
              <input v-model="grantDraft.expiresAt" type="datetime-local" :disabled="!canEditSelectedGrant" />
            </label>
            <div class="expiry-shortcuts" aria-label="有效期快捷设置">
              <button type="button" :disabled="!canEditSelectedGrant" @click="setExpiryDays(7)">7 天</button>
              <button type="button" :disabled="!canEditSelectedGrant" @click="setExpiryDays(30)">30 天</button>
              <button type="button" :disabled="!canEditSelectedGrant" @click="setExpiryDays(90)">90 天</button>
              <button
                type="button"
                :disabled="!canEditSelectedGrant"
                :class="{ 'is-active': !grantDraft.expiresAt }"
                @click="clearExpiry"
              >
                长期有效
              </button>
            </div>
          </div>
        </section>

        <section v-if="selectedUser.updated_at" class="grant-audit" aria-label="授权记录">
          <div>
            <span>授权操作人</span>
            <strong>{{ selectedUser.granted_by_name || "系统" }}</strong>
          </div>
          <div>
            <span>最后更新时间</span>
            <strong>{{ formatDateTime(selectedUser.updated_at) }}</strong>
          </div>
          <div>
            <span>授权版本</span>
            <strong>#{{ selectedUser.authorization_version }}</strong>
          </div>
          <div class="grant-audit__capabilities">
            <span>当前能力</span>
            <p v-if="selectedUser.capabilities.length">
              <code v-for="capability in selectedUser.capabilities" :key="capability">{{ capability }}</code>
            </p>
            <strong v-else>由权限级别自动计算</strong>
          </div>
        </section>

        <footer class="grant-actions">
          <div class="grant-actions__feedback" aria-live="polite">
            <p v-if="selectedUser.account_status !== 'active'">
              账号当前不可用；可撤销已有权限，但不能新增或更新授权。
            </p>
            <p v-else-if="updateGrantMutation.isSuccess.value" class="is-success">
              <CheckCircleOutlined aria-hidden="true" />高级能力配置已保存。
            </p>
            <p v-else-if="updateGrantMutation.isError.value" class="is-error" role="alert">
              {{ updateGrantMutation.error.value?.message || "保存失败，请稍后重试。" }}
            </p>
            <p v-else-if="revokeGrantMutation.isError.value" class="is-error" role="alert">
              {{ revokeGrantMutation.error.value?.message || "撤销失败，请稍后重试。" }}
            </p>
            <p v-else>所有操作都会写入后台审计记录。</p>
          </div>
          <UiButton
            v-if="selectedUser.access_level"
            tone="danger"
            :disabled="mutationPending"
            @click="confirmRevokeGrant"
          >
            <StopOutlined aria-hidden="true" />撤销高级能力
          </UiButton>
          <UiButton :disabled="mutationPending || !canEditSelectedGrant" @click="saveGrant">
            <KeyOutlined aria-hidden="true" />
            {{ updateGrantMutation.isPending.value ? "保存中…" : selectedUser.access_level ? "保存能力" : "配置能力" }}
          </UiButton>
        </footer>
      </article>

      <div v-else-if="!grantsQuery.isLoading.value && !grantsQuery.isError.value" class="grant-editor-empty">
        <LockOutlined aria-hidden="true" />
        <strong>选择一位用户</strong>
        <p>在左侧搜索并选择账号，然后配置独立的 FableSpace 高级能力。</p>
      </div>
    </div>
  </section>
</template>

<style scoped lang="scss" src="./AdminFableSpaceAccessPanel.scss"></style>
