<script setup lang="ts">
import { computed, ref, watch } from "vue";

import type { BoardDefaultSort, BoardNotificationLevel, BoardSummary } from "@/entities/board/model";
import { ApiError } from "@/shared/api/client";
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";

import {
  useBoardSettings,
  useBoards,
  useRemoveBoardMember,
  useUpdateBoardMember,
  useUpdateBoardSettings,
} from "../queries";

const props = defineProps<{
  board: BoardSummary;
}>();

const settingsQuery = useBoardSettings(() => props.board.slug, true);
const boardsQuery = useBoards();
const updateSettings = useUpdateBoardSettings(() => props.board.slug);
const updateMember = useUpdateBoardMember(() => props.board.slug);
const removeMember = useRemoveBoardMember(() => props.board.slug);

const parentBoardId = ref("");
const requiredTags = ref("");
const allowedTags = ref("");
const postTemplate = ref("");
const defaultNotificationLevel = ref<BoardNotificationLevel>("normal");
const defaultSort = ref<BoardDefaultSort>("latest");
const memberUsername = ref("");
const memberRole = ref<"follower" | "moderator">("moderator");
const settingsNotice = ref("");
const settingsError = ref("");
const memberNotice = ref("");
const memberError = ref("");

const parentCandidates = computed(() =>
  (boardsQuery.data.value ?? []).filter((board) => board.id !== props.board.id),
);
const members = computed(() => settingsQuery.data.value?.members ?? []);

watch(
  () => settingsQuery.data.value?.board,
  (board) => {
    if (!board) {
      return;
    }

    parentBoardId.value = board.parent_board_id ?? "";
    requiredTags.value = joinTags(board.required_tags);
    allowedTags.value = joinTags(board.allowed_tags);
    postTemplate.value = board.post_template ?? "";
    defaultNotificationLevel.value = board.default_notification_level;
    defaultSort.value = board.default_sort;
  },
  { immediate: true },
);

async function saveSettings() {
  settingsNotice.value = "";
  settingsError.value = "";
  try {
    await updateSettings.mutateAsync({
      parent_board_id: parentBoardId.value || null,
      required_tags: parseTags(requiredTags.value),
      allowed_tags: parseTags(allowedTags.value),
      post_template: postTemplate.value.trim() || null,
      default_notification_level: defaultNotificationLevel.value,
      default_sort: defaultSort.value,
    });
    settingsNotice.value = "版块策略已保存。";
  } catch (error) {
    settingsError.value = boardManagementError(error);
  }
}

async function saveMember() {
  memberNotice.value = "";
  memberError.value = "";
  const username = memberUsername.value.trim();
  if (!username) {
    memberError.value = "请输入成员用户名。";
    return;
  }

  try {
    await updateMember.mutateAsync({
      username,
      payload: { role: memberRole.value },
    });
    memberUsername.value = "";
    memberNotice.value = "成员角色已更新。";
  } catch (error) {
    memberError.value = boardManagementError(error);
  }
}

async function removeExistingMember(username: string) {
  memberNotice.value = "";
  memberError.value = "";
  try {
    await removeMember.mutateAsync(username);
    memberNotice.value = `已移除 ${username}。`;
  } catch (error) {
    memberError.value = boardManagementError(error);
  }
}

function parseTags(value: string): string[] {
  return Array.from(
    new Set(
      value
        .split(/[，,]/)
        .map((tag) => tag.trim())
        .filter(Boolean),
    ),
  );
}

function joinTags(value: string[]): string {
  return value.join(", ");
}

function boardManagementError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === "required_tags_not_allowed") {
      return "必填标签必须同时出现在允许标签列表里。";
    }

    if (error.code === "board_parent_cycle" || error.code === "board_parent_invalid") {
      return "父子版块不能形成循环，也不能把自己设为父版块。";
    }

    if (error.code === "board_owner_role_protected") {
      return "不能通过成员面板移除或降级版块拥有者。";
    }

    if (error.code === "user_not_found") {
      return "没有找到这个用户名。";
    }
  }

  return "保存失败，请稍后重试。";
}
</script>

<template>
  <UiCard class="board-settings-panel">
    <header>
      <div>
        <span>版块控制台</span>
        <h2>管理层级、标签策略和版主</h2>
      </div>
      <small>{{ settingsQuery.isFetching.value ? "同步中" : "仅 owner / admin 可见" }}</small>
    </header>

    <form class="settings-grid" @submit.prevent="saveSettings">
      <label>
        <span>父版块</span>
        <select v-model="parentBoardId">
          <option value="">顶层版块</option>
          <option v-for="candidate in parentCandidates" :key="candidate.id" :value="candidate.id">
            {{ candidate.name }}
          </option>
        </select>
      </label>

      <label>
        <span>默认排序</span>
        <select v-model="defaultSort">
          <option value="latest">最新</option>
          <option value="hot">热门</option>
          <option value="top">高信号</option>
        </select>
      </label>

      <label>
        <span>默认通知</span>
        <select v-model="defaultNotificationLevel">
          <option value="watching">关注 · 新主题提醒</option>
          <option value="tracking">跟踪 · 精简提醒</option>
          <option value="normal">普通 · 不主动提醒</option>
          <option value="muted">静音 · 不接收提醒</option>
        </select>
      </label>

      <label>
        <span>必填标签</span>
        <input v-model="requiredTags" placeholder="例如：bug, backend" />
      </label>

      <label class="settings-grid__wide">
        <span>允许标签</span>
        <input v-model="allowedTags" placeholder="留空表示不限制；用逗号分隔" />
      </label>

      <label class="settings-grid__wide">
        <span>发帖模板</span>
        <textarea
          v-model="postTemplate"
          rows="5"
          placeholder="环境：&#10;复现步骤：&#10;实际结果："
        ></textarea>
      </label>

      <p v-if="settingsNotice" class="panel-success">{{ settingsNotice }}</p>
      <p v-if="settingsError" class="panel-error">{{ settingsError }}</p>
      <UiButton type="submit" tone="primary" :disabled="updateSettings.isPending.value">
        {{ updateSettings.isPending.value ? "保存中…" : "保存版块策略" }}
      </UiButton>
    </form>

    <section class="member-manager" aria-label="版块成员角色">
      <div class="member-manager__form">
        <label>
          <span>成员用户名</span>
          <input v-model="memberUsername" placeholder="username" />
        </label>
        <label>
          <span>角色</span>
          <select v-model="memberRole">
            <option value="moderator">版主</option>
            <option value="follower">成员</option>
          </select>
        </label>
        <UiButton tone="subtle" :disabled="updateMember.isPending.value" @click="saveMember">
          更新成员
        </UiButton>
      </div>

      <div class="member-list">
        <div v-for="member in members" :key="member.user_id">
          <span>
            <strong>{{ member.username }}</strong>
            <small>{{ member.role }} · {{ member.notification_level }}</small>
          </span>
          <UiButton
            v-if="member.role !== 'owner'"
            tone="ghost"
            :disabled="removeMember.isPending.value"
            @click="removeExistingMember(member.username)"
          >
            移除
          </UiButton>
        </div>
      </div>

      <p v-if="memberNotice" class="panel-success">{{ memberNotice }}</p>
      <p v-if="memberError" class="panel-error">{{ memberError }}</p>
    </section>
  </UiCard>
</template>

<style scoped lang="scss" src="./BoardSettingsPanel.scss"></style>

