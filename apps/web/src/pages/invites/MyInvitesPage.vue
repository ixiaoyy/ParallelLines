<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRouter } from "vue-router";

import { useCreateBoard } from "@/features/boards/queries";
import { useCreateBoardInvite, useInviteAction, useMyBoardInvites } from "@/features/invites/queries";
import { hasAccessToken } from "@/shared/api/client";
import { relativeTime } from "@/shared/lib/format";
import { boardToneClass } from "@/shared/theme/boardPalette";
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";
import UiEmptyState from "@/shared/ui/EmptyState.vue";

const router = useRouter();
const invitesQuery = useMyBoardInvites();
const createBoardMutation = useCreateBoard();
const createInviteMutation = useCreateBoardInvite();
const inviteAction = useInviteAction();

const boardName = ref("");
const boardSlug = ref("");
const boardDescription = ref("");
const selectedBoardId = ref("");
const inviteUsername = ref("");
const statusMessage = ref("");

const data = computed(() => invitesQuery.data.value);
const ownedBoards = computed(() => data.value?.ownedBoards ?? []);
const pendingReceivedInvites = computed(() =>
  (data.value?.received ?? []).filter((invite) => invite.status === "pending"),
);
const pendingManagedInvites = computed(() =>
  (data.value?.managed ?? []).filter((invite) => invite.status === "pending"),
);
const selectedBoard = computed(() =>
  ownedBoards.value.find((board) => board.id === selectedBoardId.value),
);
const canCreateBoard = computed(() => Boolean(boardName.value.trim() && boardSlug.value.trim()));
const canSendInvite = computed(() => Boolean(selectedBoardId.value && inviteUsername.value.trim()));

watch(
  ownedBoards,
  (boards) => {
    if (!selectedBoardId.value && boards.length) {
      selectedBoardId.value = boards[0].id;
    }
  },
  { immediate: true },
);

function requireLogin() {
  if (hasAccessToken()) {
    return true;
  }
  void router.push({ name: "auth", query: { redirect: "/invites" } });
  return false;
}

async function createPrivateBoard() {
  if (!requireLogin() || !boardName.value.trim() || !boardSlug.value.trim()) {
    return;
  }
  statusMessage.value = "";
  try {
    const board = await createBoardMutation.mutateAsync({
      slug: boardSlug.value.trim(),
      name: boardName.value.trim(),
      description: boardDescription.value.trim() || "仅受邀成员可见的私密讨论空间。",
      color: "#409EFF",
      visibility: "private",
    });
    boardName.value = "";
    boardSlug.value = "";
    boardDescription.value = "";
    selectedBoardId.value = board.id;
    await invitesQuery.refetch();
    statusMessage.value = "邀请版块已创建。";
  } catch {
    statusMessage.value = "创建失败，请检查 slug 是否重复或稍后重试。";
  }
}

async function sendInvite() {
  if (!requireLogin() || !selectedBoardId.value || !inviteUsername.value.trim()) {
    return;
  }
  statusMessage.value = "";
  try {
    await createInviteMutation.mutateAsync({
      board_id: selectedBoardId.value,
      username: inviteUsername.value.trim(),
    });
    inviteUsername.value = "";
    statusMessage.value = "邀请已发送。";
  } catch {
    statusMessage.value = "邀请发送失败，请确认用户名存在且你是版块拥有者。";
  }
}

async function runInviteAction(inviteId: string, action: "accept" | "decline" | "revoke") {
  if (!requireLogin()) {
    return;
  }
  try {
    await inviteAction.mutateAsync({ inviteId, action });
    statusMessage.value =
      action === "accept" ? "已加入邀请版块。" : action === "decline" ? "已拒绝邀请。" : "邀请已撤回。";
  } catch {
    statusMessage.value = "操作失败，邀请可能已被处理。";
  }
}
</script>

<template>
  <div class="my-invites-page">
    <section class="invites-hero" aria-labelledby="my-invites-title">
      <div class="invites-hero__copy">
        <span class="panel-kicker">邀请中心</span>
        <h1 id="my-invites-title">先创建空间，再邀请成员。</h1>
        <p>邀请版块只对成员可见。你可以创建私密讨论空间，按用户名邀请成员，也可以处理别人发来的加入邀请。</p>
      </div>
      <div class="invites-hero__side">
        <RouterLink class="hero-link" :to="{ name: 'board-directory' }">浏览公开版块</RouterLink>
        <dl v-if="hasAccessToken()" class="invite-stats" aria-label="邀请概览">
          <div>
            <dt>{{ ownedBoards.length }}</dt>
            <dd>我的空间</dd>
          </div>
          <div>
            <dt>{{ pendingReceivedInvites.length }}</dt>
            <dd>待处理</dd>
          </div>
          <div>
            <dt>{{ pendingManagedInvites.length }}</dt>
            <dd>已发邀请</dd>
          </div>
        </dl>
      </div>
    </section>

    <UiEmptyState
      v-if="!hasAccessToken()"
      title="请先登录"
      description="登录后可以查看收到的邀请、创建邀请版块并管理成员邀请。"
    >
      <RouterLink class="empty-link" :to="{ name: 'auth', query: { redirect: '/invites' } }">
        登录/注册
      </RouterLink>
    </UiEmptyState>

    <div v-else class="invites-workbench">
      <main class="invites-primary">
        <UiCard class="invite-panel invite-panel--create">
          <div class="panel-head">
            <div>
              <span>第一步</span>
              <h2>创建邀请版块</h2>
            </div>
            <p>先建一个私密空间，再把成员拉进来。</p>
          </div>
          <form class="create-board-form" @submit.prevent="createPrivateBoard">
            <label>
              <span>版块名称</span>
              <input v-model="boardName" placeholder="例如：内部排障实验室" />
            </label>
            <label>
              <span>访问标识</span>
              <input v-model="boardSlug" placeholder="private-lab" />
              <small>用于版块 URL，建议使用小写英文、数字或连字符。</small>
            </label>
            <label class="form-field--wide">
              <span>说明</span>
              <textarea v-model="boardDescription" rows="3" placeholder="这个版块讨论什么？" />
            </label>
            <UiButton
              class="form-submit"
              type="submit"
              tone="primary"
              :disabled="!canCreateBoard || createBoardMutation.isPending.value"
            >
              {{ createBoardMutation.isPending.value ? "创建中…" : "创建邀请版块" }}
            </UiButton>
          </form>
        </UiCard>

        <UiCard class="invite-panel invite-panel--members">
          <div class="panel-head">
            <div>
              <span>第二步</span>
              <h2>邀请成员</h2>
            </div>
            <p v-if="selectedBoard">当前空间：{{ selectedBoard.name }}</p>
          </div>
          <form class="invite-form" @submit.prevent="sendInvite">
            <label>
              <span>选择邀请版块</span>
              <select v-model="selectedBoardId">
                <option v-for="board in ownedBoards" :key="board.id" :value="board.id">
                  {{ board.name }}
                </option>
              </select>
            </label>
            <label>
              <span>用户名</span>
              <input v-model="inviteUsername" placeholder="输入已注册用户名" />
            </label>
            <UiButton
              class="form-submit"
              type="submit"
              tone="primary"
              :disabled="!canSendInvite || createInviteMutation.isPending.value"
            >
              {{ createInviteMutation.isPending.value ? "发送中…" : "发送邀请" }}
            </UiButton>
          </form>
          <p v-if="!ownedBoards.length" class="panel-state panel-state--guide">
            还没有可邀请成员的空间。请先在上方创建一个邀请版块。
          </p>
        </UiCard>
      </main>

      <aside class="invites-secondary" aria-label="邀请状态">
        <UiCard class="invite-panel invite-panel--received">
          <div class="panel-head">
            <div>
              <span>收到的邀请</span>
              <h2>待处理邀请</h2>
            </div>
          </div>
          <p v-if="invitesQuery.isLoading.value" class="panel-state">正在加载邀请…</p>
          <p v-else-if="invitesQuery.isError.value" class="panel-state panel-state--error">
            邀请列表暂时不可用。
          </p>
          <p v-else-if="!pendingReceivedInvites.length" class="panel-state panel-state--empty">
            暂无待处理邀请。
          </p>
          <article
            v-for="invite in pendingReceivedInvites"
            :key="invite.id"
            class="invite-card"
            :class="boardToneClass(invite.boardSlug)"
          >
            <span class="invite-mark" aria-hidden="true"></span>
            <div>
              <strong>{{ invite.boardName }}</strong>
              <p>{{ invite.boardDescription }}</p>
              <small>{{ invite.inviterName }} 邀请你加入 · {{ relativeTime(invite.createdAt) }}</small>
            </div>
            <div class="invite-actions">
              <UiButton tone="primary" :disabled="inviteAction.isPending.value" @click="runInviteAction(invite.id, 'accept')">
                接受
              </UiButton>
              <UiButton tone="ghost" :disabled="inviteAction.isPending.value" @click="runInviteAction(invite.id, 'decline')">
                拒绝
              </UiButton>
            </div>
          </article>
        </UiCard>

        <UiCard class="invite-panel invite-panel--managed">
          <div class="panel-head">
            <div>
              <span>我发出的邀请</span>
              <h2>等待对方处理</h2>
            </div>
          </div>
          <div v-if="pendingManagedInvites.length" class="managed-list" aria-label="待处理邀请">
            <article v-for="invite in pendingManagedInvites" :key="invite.id" class="managed-item">
              <div>
                <strong>{{ invite.inviteeName }}</strong>
                <span>{{ invite.boardName }} · {{ relativeTime(invite.createdAt) }}</span>
              </div>
              <UiButton tone="ghost" :disabled="inviteAction.isPending.value" @click="runInviteAction(invite.id, 'revoke')">
                撤回
              </UiButton>
            </article>
          </div>
          <p v-else class="panel-state panel-state--empty">暂无等待处理的成员邀请。</p>
        </UiCard>
      </aside>
    </div>

    <p v-if="statusMessage" class="invite-status" role="status">{{ statusMessage }}</p>
  </div>
</template>

<style scoped lang="scss" src="./MyInvitesPage.scss"></style>
