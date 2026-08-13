<script setup lang="ts">
import {
  ArrowRightOutlined,
  LockOutlined,
} from "@ant-design/icons-vue";
import { computed, defineAsyncComponent } from "vue";

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
        <a class="play-option" href="https://fable.pingxingxian.space/">
          <span class="play-option__mark play-option__mark--private" aria-hidden="true">
            <LockOutlined />
          </span>
          <span class="play-option__copy">
            <strong>私密空间</strong>
            <small>直接进入</small>
          </span>
          <span class="play-option__action">
            进入
            <ArrowRightOutlined aria-hidden="true" />
          </span>
        </a>

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
