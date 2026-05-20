<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRouter } from "vue-router";

import { useCreateBoard } from "@/features/boards/queries";
import { useCreateBoardInvite, useInviteAction, useMyBoardInvites } from "@/features/invites/queries";
import { hasAccessToken } from "@/shared/api/client";
import { relativeTime } from "@/shared/lib/format";
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
const pendingManagedInvites = computed(() =>
  (data.value?.managed ?? []).filter((invite) => invite.status === "pending"),
);

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
      color: "#005AA8",
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
      <div>
        <span>邀请版块</span>
        <h1 id="my-invites-title">管理你的私密讨论空间。</h1>
        <p>接受收到的版块邀请，或创建自己的邀请版块并按用户名邀请成员。</p>
      </div>
      <RouterLink class="hero-link" :to="{ name: 'board-directory' }">浏览公开版块</RouterLink>
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

    <div v-else class="invites-layout">
      <main class="invites-main">
        <UiCard class="invite-panel">
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
          <p v-else-if="!data?.received.length" class="panel-state">暂无待处理邀请。</p>
          <article
            v-for="invite in data?.received"
            :key="invite.id"
            class="invite-card"
            :style="{ '--board-color': invite.boardColor }"
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

        <UiCard class="invite-panel">
          <div class="panel-head">
            <div>
              <span>我管理的邀请</span>
              <h2>邀请成员</h2>
            </div>
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
            <UiButton type="submit" tone="primary" :disabled="!selectedBoardId || !inviteUsername.trim() || createInviteMutation.isPending.value">
              {{ createInviteMutation.isPending.value ? "发送中…" : "发送邀请" }}
            </UiButton>
          </form>
          <p v-if="!ownedBoards.length" class="panel-state">先创建一个邀请版块，再邀请成员。</p>
          <div class="managed-list" aria-label="待处理邀请">
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
        </UiCard>
      </main>

      <aside class="invites-side">
        <UiCard class="invite-panel">
          <div class="panel-head">
            <div>
              <span>创建空间</span>
              <h2>新的邀请版块</h2>
            </div>
          </div>
          <form class="create-board-form" @submit.prevent="createPrivateBoard">
            <label>
              <span>版块名称</span>
              <input v-model="boardName" placeholder="例如：内部排障实验室" />
            </label>
            <label>
              <span>URL Slug</span>
              <input v-model="boardSlug" placeholder="private-lab" />
            </label>
            <label>
              <span>说明</span>
              <textarea v-model="boardDescription" rows="4" placeholder="这个版块讨论什么？" />
            </label>
            <UiButton type="submit" tone="primary" :disabled="!boardName.trim() || !boardSlug.trim() || createBoardMutation.isPending.value">
              {{ createBoardMutation.isPending.value ? "创建中…" : "创建邀请版块" }}
            </UiButton>
          </form>
        </UiCard>
      </aside>
    </div>

    <p v-if="statusMessage" class="invite-status" role="status">{{ statusMessage }}</p>
  </div>
</template>

<style scoped lang="scss" src="./MyInvitesPage.scss"></style>
