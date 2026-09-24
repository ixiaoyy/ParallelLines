<script setup lang="ts">
import {
  ArrowRightOutlined,
  LockOutlined,
} from "@ant-design/icons-vue";
import { computed, defineAsyncComponent, onBeforeUnmount, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { requestFableSpaceSsoTicket } from "@/features/auth/api";
import { useBoards } from "@/features/boards/queries";
import { useTags } from "@/features/tags/queries";
import {
  readCachedHomeRailBoards,
  readCachedHomeRailTags,
} from "@/pages/home/homeRailCache";
import { hasAccessToken } from "@/shared/api/client";
import { useMediaQuery } from "@/shared/lib/useMediaQuery";
import { readRouteParam } from "@/shared/router/params";

const ForumLeftRail = defineAsyncComponent(() =>
  import("@/features/navigation/components/ForumLeftRail.vue"),
);

const route = useRoute();
const router = useRouter();
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

const TICKET_TIMEOUT_MS = 8_000;
const NAVIGATION_TIMEOUT_MS = 8_000;
const isFableSpaceLaunching = ref(false);
const fableSpaceLaunchError = ref("");
let ticketController: AbortController | null = null;
let ticketTimer: number | null = null;
let navigationTimer: number | null = null;
let pageDisposed = false;
const MIRROR_SSO_QUERY_KEY = "mirror_sso";

// Clears only timers and requests owned by the FableSpace launch control.
function clearFableSpaceLaunch(): void {
  ticketController?.abort();
  ticketController = null;
  if (ticketTimer !== null) window.clearTimeout(ticketTimer);
  if (navigationTimer !== null) window.clearTimeout(navigationTimer);
  ticketTimer = null;
  navigationTimer = null;
}

// Suspends this page's launch work once the browser starts leaving the document.
// Parameters: none. Return value: none. Side effects: blocks stale callbacks and clears owned work.
function handlePageHide(): void {
  pageDisposed = true;
  clearFableSpaceLaunch();
}

// Restores the private-space entry after this document returns from the browser back-forward cache.
// Key parameter is the browser page transition; return value is none. Side effect: resets launch UI state.
function handlePageShow(event: PageTransitionEvent): void {
  if (!event.persisted) return;
  pageDisposed = false;
  isFableSpaceLaunching.value = false;
  fableSpaceLaunchError.value = "";
}

// Requests one single-use forum ticket and navigates to its server-authorized Mirror Island callback.
async function launchFableSpace(): Promise<void> {
  if (isFableSpaceLaunching.value) return;
  clearFableSpaceLaunch();
  fableSpaceLaunchError.value = "";
  isFableSpaceLaunching.value = true;
  ticketController = new AbortController();
  ticketTimer = window.setTimeout(() => ticketController?.abort(), TICKET_TIMEOUT_MS);

  try {
    const ticket = await requestFableSpaceSsoTicket(ticketController.signal);
    if (ticketTimer !== null) window.clearTimeout(ticketTimer);
    ticketTimer = null;
    navigationTimer = window.setTimeout(() => {
      if (pageDisposed) return;
      isFableSpaceLaunching.value = false;
      fableSpaceLaunchError.value = "跳转未完成，请重试。";
    }, NAVIGATION_TIMEOUT_MS);
    window.location.assign(ticket.redirect_url);
  } catch {
    if (pageDisposed) return;
    const timedOut = ticketController?.signal.aborted === true;
    isFableSpaceLaunching.value = false;
    fableSpaceLaunchError.value = timedOut
      ? "连接镜像岛超时，请重试。"
      : "暂时无法进入镜像岛，请稍后重试。";
    clearFableSpaceLaunch();
  }
}

// Resumes the Keycloak forum-account handoff once, preserving it through forum login when needed.
// Key parameters come from the current route; return value is none. Side effects: replaces the route and may launch Mirror Island.
async function resumeMirrorSsoFromRoute(): Promise<void> {
  const requested = readRouteParam(
    route.query[MIRROR_SSO_QUERY_KEY] as string | string[] | undefined,
  );
  if (requested !== "1") return;

  try {
    if (!hasAccessToken()) {
      await router.replace({ name: "auth", query: { redirect: route.fullPath } });
      return;
    }

    const query = { ...route.query };
    delete query[MIRROR_SSO_QUERY_KEY];
    await router.replace({ name: "play-hub", query });
    await launchFableSpace();
  } catch {
    if (pageDisposed) return;
    isFableSpaceLaunching.value = false;
    fableSpaceLaunchError.value = "论坛账号跳转未完成，请重试。";
  }
}

onMounted(() => {
  window.addEventListener("pagehide", handlePageHide);
  window.addEventListener("pageshow", handlePageShow);
  void resumeMirrorSsoFromRoute();
});

onBeforeUnmount(() => {
  pageDisposed = true;
  window.removeEventListener("pagehide", handlePageHide);
  window.removeEventListener("pageshow", handlePageShow);
  clearFableSpaceLaunch();
});
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
        <div>
          <span class="play-hub-header__eyebrow">平行线 · 游乐场</span>
          <h1 id="play-hub-title">游乐场</h1>
          <p>今天玩点什么？选一款喜欢的游戏，随时开始。</p>
        </div>
        <span class="play-hub-header__count">5 个可玩项目</span>
      </header>

      <div class="play-gallery" aria-label="可玩项目">
        <RouterLink class="play-feature-card" :to="{ name: 'play-generals-soldiers' }">
          <span class="play-feature-card__label">新加入 · Q 版策略对弈</span>
          <strong>将军战小兵</strong>
          <p>选将军突围，或带领小兵围困对手。喵喵酱已经摆好棋盘。</p>
          <span class="play-feature-card__action">开始对弈 <ArrowRightOutlined aria-hidden="true" /></span>
          <span class="play-feature-card__pieces" aria-hidden="true">
            <i><img src="/games/generals-soldiers/general-chibi.png" alt="" width="320" height="320" /></i>
            <i><img src="/games/generals-soldiers/soldier-chibi.png" alt="" width="320" height="320" /></i>
          </span>
          <img class="play-feature-card__character" src="/games/generals-soldiers/miaomiao-chibi.png" alt="" width="760" height="827" />
        </RouterLink>

        <RouterLink class="play-game-card play-game-card--melon" :to="{ name: 'play-melon' }">
          <span class="play-game-card__top">新加入 · 半流体合成 <ArrowRightOutlined aria-hidden="true" /></span>
          <span class="play-game-card__art" aria-hidden="true"><img src="/games/melon/mark.svg" alt="" width="48" height="48" /></span>
          <strong>瓜体实验室</strong>
          <p>让水果像果冻一样流动、碰撞、融合，合成大西瓜。</p>
          <span class="play-game-card__action">开始实验</span>
        </RouterLink>

        <RouterLink class="play-game-card play-game-card--clockout" :to="{ name: 'play-clockout' }">
          <span class="play-game-card__top">新加入 · 18 关潜行 <ArrowRightOutlined aria-hidden="true" /></span>
          <span class="play-game-card__art" aria-hidden="true"><img src="/games/clockout/scene.png" alt="" width="820" height="460" /></span>
          <strong>准点下班</strong>
          <p>躲开巡视，带上背包，赶在 18:00 前走进电梯。</p>
          <span class="play-game-card__action">开始闯关</span>
        </RouterLink>

        <RouterLink class="play-game-card play-game-card--match" :to="{ name: 'play-match3' }">
          <span class="play-game-card__top">轻松休闲 <ArrowRightOutlined aria-hidden="true" /></span>
          <span class="play-game-card__art" aria-hidden="true"><img src="/match3-game-mark.png" alt="" width="96" height="96" /></span>
          <strong>平行消消乐</strong>
          <p>打开即玩，来一局轻松的消除。</p>
          <span class="play-game-card__action">开始游戏</span>
        </RouterLink>

        <a class="play-game-card play-game-card--private" href="https://fable.pingxingxian.space/">
          <span class="play-game-card__top">独立空间 <ArrowRightOutlined aria-hidden="true" /></span>
          <span class="play-game-card__art play-game-card__art--private" aria-hidden="true"><LockOutlined /></span>
          <strong>私密空间</strong>
          <p>前往独立空间，继续探索。</p>
          <span class="play-game-card__action">直接进入</span>
        </a>
      </div>

      <p v-if="fableSpaceLaunchError" class="play-hub-error" role="alert">{{ fableSpaceLaunchError }}</p>
    </section>
  </div>
</template>

<style scoped lang="scss" src="./PlayHubPage.scss"></style>
