<script setup lang="ts">
import {
  ArrowRightOutlined,
  LockOutlined,
} from "@ant-design/icons-vue";
import { message } from "ant-design-vue";
import { computed, defineAsyncComponent, ref } from "vue";
import { useRouter } from "vue-router";

import { requestFableSpaceSsoTicket } from "@/features/auth/api";
import { useCurrentUser } from "@/features/auth/queries";
import { useBoards } from "@/features/boards/queries";
import { match3LaunchUrl } from "@/features/play/products";
import { useTags } from "@/features/tags/queries";
import {
  readCachedHomeRailBoards,
  readCachedHomeRailTags,
} from "@/pages/home/homeRailCache";
import { useMediaQuery } from "@/shared/lib/useMediaQuery";

const ForumLeftRail = defineAsyncComponent(() =>
  import("@/features/navigation/components/ForumLeftRail.vue"),
);

const router = useRouter();
const currentUserQuery = useCurrentUser();
const currentUser = computed(() => currentUserQuery.data.value);
const openingPrivateSpace = ref(false);
const match3Url = match3LaunchUrl("play-hub");
const isDesktopRailVisible = useMediaQuery("(min-width: 981px)", true);
const boardsQuery = useBoards(isDesktopRailVisible);
const tagsQuery = useTags(30, isDesktopRailVisible);
const cachedRailBoards = readCachedHomeRailBoards();
const cachedRailTags = readCachedHomeRailTags();
const railBoards = computed(
  () => boardsQuery.data.value ?? (boardsQuery.isLoading.value ? cachedRailBoards : []),
);
const railTags = computed(
  () => (tagsQuery.data.value ?? (tagsQuery.isLoading.value ? cachedRailTags : [])).slice(0, 10),
);
const railBoardsLoading = computed(
  () => boardsQuery.isLoading.value && cachedRailBoards.length === 0,
);
const railTagsLoading = computed(
  () => tagsQuery.isLoading.value && cachedRailTags.length === 0,
);

// Sends guests to authentication and signed-in users through the existing one-time SSO handoff.
// Parameters: none. Return value resolves after routing, redirect, or error feedback; side effect changes browser location.
async function openPrivateSpace(): Promise<void> {
  if (!currentUser.value) {
    await router.push({ name: "auth", query: { redirect: "/play" } });
    return;
  }
  if (openingPrivateSpace.value) {
    return;
  }

  openingPrivateSpace.value = true;
  try {
    const ticket = await requestFableSpaceSsoTicket();
    window.location.assign(ticket.redirect_url);
  } catch {
    message.error("私密空间暂时无法进入，请稍后再试");
    openingPrivateSpace.value = false;
  }
}
</script>

<template>
  <div class="play-hub-layout">
    <ForumLeftRail
      v-if="isDesktopRailVisible"
      :boards="railBoards"
      :tags="railTags"
      :boards-loading="railBoardsLoading"
      :boards-error="boardsQuery.isError.value"
      :tags-loading="railTagsLoading"
      :tags-error="tagsQuery.isError.value"
    />

    <section class="play-hub-page" aria-labelledby="play-hub-title">
      <header class="play-hub-header">
        <h1 id="play-hub-title">游乐场</h1>
        <span>2 个项目</span>
      </header>

      <section class="play-options" aria-label="可玩项目">
        <button
          class="play-option"
          type="button"
          :disabled="openingPrivateSpace"
          :aria-busy="openingPrivateSpace"
          @click="openPrivateSpace"
        >
          <span class="play-option__mark play-option__mark--private" aria-hidden="true">
            <LockOutlined />
          </span>
          <span class="play-option__copy">
            <strong>私密空间</strong>
            <small>{{ currentUser ? "使用当前账号进入" : "登录后进入" }}</small>
          </span>
          <span class="play-option__action">
            {{ openingPrivateSpace ? "正在进入…" : "进入" }}
            <ArrowRightOutlined aria-hidden="true" />
          </span>
        </button>

        <a class="play-option" :href="match3Url">
          <span class="play-option__mark play-option__mark--match" aria-hidden="true">
            <img src="/match3-game-mark.png" alt="" width="64" height="64" />
          </span>
          <span class="play-option__copy">
            <strong>平行消消乐</strong>
            <small>打开即玩</small>
          </span>
          <span class="play-option__action">
            开始
            <ArrowRightOutlined aria-hidden="true" />
          </span>
        </a>
      </section>
    </section>
  </div>
</template>

<style scoped lang="scss" src="./PlayHubPage.scss"></style>
