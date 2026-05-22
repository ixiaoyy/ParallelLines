<script setup lang="ts">
import { computed, ref } from "vue";

import { useCurrentUser } from "@/features/auth/queries";
import {
  reviewableStatusLabel,
  reviewableTypeLabel,
} from "@/features/moderation/model";
import type { ReviewableResponse } from "@/features/moderation/model";
import {
  useAppealReviewableMutation,
  useMyReviewables,
} from "@/features/moderation/queries";
import { hasAccessToken } from "@/shared/api/client";
import { relativeTime } from "@/shared/lib/format";
import { topicDetailRoute } from "@/shared/router/topicRoutes";
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";

const currentUserQuery = useCurrentUser();
const reviewablesQuery = useMyReviewables();
const appealMutation = useAppealReviewableMutation();

const activeAppealId = ref<string | null>(null);
const appealReason = ref("");
const appealNotice = ref("");
const appealError = ref("");

const currentUser = computed(() => currentUserQuery.data.value);
const hasToken = computed(() => hasAccessToken());
const reviewables = computed(() => reviewablesQuery.data.value ?? []);
const isAppealPending = computed(() => appealMutation.isPending.value);

function openAppeal(reviewable: ReviewableResponse) {
  activeAppealId.value = reviewable.id;
  appealReason.value = "";
  appealNotice.value = "";
  appealError.value = "";
}

function cancelAppeal() {
  activeAppealId.value = null;
  appealReason.value = "";
  appealError.value = "";
}

function submitAppeal(reviewable: ReviewableResponse) {
  const reason = appealReason.value.trim();
  if (reason.length < 4) {
    appealError.value = "请补充至少 4 个字符的申诉理由。";
    return;
  }

  appealMutation.mutate(
    { reviewableId: reviewable.id, payload: { reason } },
    {
      onSuccess: () => {
        activeAppealId.value = null;
        appealReason.value = "";
        appealNotice.value = "申诉已提交，审核员会重新查看此项。";
        appealError.value = "";
      },
      onError: (error) => {
        appealError.value = error.message || "申诉提交失败，请稍后重试。";
      },
    },
  );
}

function reviewableTitle(reviewable: ReviewableResponse) {
  return readString(reviewable.data.title) ?? reviewable.source_summary;
}

function reviewableExcerpt(reviewable: ReviewableResponse) {
  return readString(reviewable.data.excerpt) ?? "此审核项暂无公开摘要。";
}

function reviewableRoute(reviewable: ReviewableResponse) {
  const topicSlug = readString(reviewable.data.topic_slug);
  if (reviewable.topic_id && topicSlug) {
    const postNumber = readNumber(reviewable.data.post_number);
    return topicDetailRoute({
      id: reviewable.topic_id,
      slug: topicSlug,
      hash: postNumber ? `post-${postNumber}` : null,
    });
  }

  const boardSlug = readString(reviewable.data.board_slug);
  return boardSlug ? `/b/${boardSlug}` : "/boards";
}

function readString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function readNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}
</script>

<template>
  <div class="my-reviewables-page">
    <section class="reviewables-hero" aria-labelledby="my-reviewables-title">
      <div>
        <span class="panel-kicker">My moderation cases</span>
        <h1 id="my-reviewables-title">我的审核与申诉</h1>
        <p>查看你提交或与你相关的待审内容、处理结果，并在可申诉时补充说明。</p>
      </div>
      <RouterLink class="hero-link" to="/boards">返回社区</RouterLink>
    </section>

    <UiCard v-if="!hasToken" class="reviewables-empty">
      <strong>需要登录后查看</strong>
      <span>登录后可以看到与你相关的审核项和申诉入口。</span>
    </UiCard>

    <UiCard v-else-if="reviewablesQuery.isError.value" class="reviewables-empty">
      <strong>暂时无法加载审核记录</strong>
      <span>请稍后重试，或通过通知中心重新进入。</span>
    </UiCard>

    <template v-else>
      <p v-if="appealNotice" class="reviewables-success">{{ appealNotice }}</p>
      <p v-if="appealError" class="reviewables-error">{{ appealError }}</p>

      <div v-if="reviewables.length" class="reviewables-list">
        <article v-for="item in reviewables" :key="item.id" class="reviewable-card">
          <header>
            <div>
              <span class="reviewable-meta">
                {{ reviewableTypeLabel(item.type) }} · {{ reviewableStatusLabel(item.status) }} ·
                {{ relativeTime(item.created_at) }}
              </span>
              <h2>{{ reviewableTitle(item) }}</h2>
            </div>
            <RouterLink :to="reviewableRoute(item)">查看上下文</RouterLink>
          </header>

          <p>{{ reviewableExcerpt(item) }}</p>
          <dl>
            <div>
              <dt>当前状态</dt>
              <dd>{{ reviewableStatusLabel(item.status) }}</dd>
            </div>
            <div>
              <dt>发起账号</dt>
              <dd>{{ item.created_by_name || currentUser?.username || "我" }}</dd>
            </div>
            <div>
              <dt>处理人</dt>
              <dd>{{ item.resolved_by_name || item.assigned_to_name || "待分配" }}</dd>
            </div>
          </dl>

          <form
            v-if="activeAppealId === item.id"
            class="appeal-form"
            @submit.prevent="submitAppeal(item)"
          >
            <label>
              <span>申诉理由</span>
              <textarea
                v-model="appealReason"
                rows="4"
                placeholder="说明为什么你认为处理结果需要复核"
              />
            </label>
            <div class="appeal-actions">
              <UiButton type="submit" tone="success" :disabled="isAppealPending">
                提交申诉
              </UiButton>
              <UiButton tone="ghost" :disabled="isAppealPending" @click="cancelAppeal">
                取消
              </UiButton>
            </div>
          </form>

          <footer v-else>
            <UiButton
              v-if="item.appeal_available"
              tone="subtle"
              :disabled="isAppealPending"
              @click="openAppeal(item)"
            >
              发起申诉
            </UiButton>
            <span v-else>当前状态暂不可申诉。</span>
          </footer>
        </article>
      </div>

      <UiCard v-else class="reviewables-empty">
        <strong>暂无与你相关的审核项</strong>
        <span>如果内容进入待审或处理完成，相关记录会显示在这里。</span>
      </UiCard>
    </template>
  </div>
</template>

<style scoped lang="scss" src="./MyReviewablesPage.scss"></style>
