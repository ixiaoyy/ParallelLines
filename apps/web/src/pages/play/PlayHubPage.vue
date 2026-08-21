<script setup lang="ts">
import {
  ArrowRightOutlined,
  LockOutlined,
} from "@ant-design/icons-vue";
import { computed, defineAsyncComponent, onBeforeUnmount, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { requestFableSpaceSsoTicket } from "@/features/auth/api";
import { useBoards } from "@/features/boards/queries";
import { match3LaunchUrl } from "@/features/play/products";
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

const match3Url = match3LaunchUrl("play-hub");
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
        <h1 id="play-hub-title">游乐场</h1>
        <span>2 个项目</span>
      </header>

      <section class="play-options" aria-label="可玩项目">
        <button
          class="play-option"
          type="button"
          :disabled="isFableSpaceLaunching"
          :aria-busy="isFableSpaceLaunching"
          @click="launchFableSpace"
        >
          <span class="play-option__mark play-option__mark--private" aria-hidden="true">
            <LockOutlined />
          </span>
          <span class="play-option__copy">
            <strong>私密空间</strong>
            <small>{{ isFableSpaceLaunching ? "正在建立安全登录…" : "使用论坛账号进入" }}</small>
          </span>
          <span class="play-option__action">
            {{ isFableSpaceLaunching ? "请稍候" : "进入" }}
            <ArrowRightOutlined aria-hidden="true" />
          </span>
        </button>

        <p v-if="fableSpaceLaunchError" class="play-options__error" role="alert">
          {{ fableSpaceLaunchError }}
        </p>

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
