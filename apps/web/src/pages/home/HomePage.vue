<script setup lang="ts">
import { ref } from "vue";

import BoardCard from "@/features/boards/components/BoardCard.vue";
import PostItem from "@/features/posts/components/PostItem.vue";
import ComposerDrawer from "@/features/topics/components/ComposerDrawer.vue";
import TopicList from "@/features/topics/components/TopicList.vue";
import { boards, highlightedPost, topics } from "@/pages/home/fixtures";
import UiBadge from "@/shared/ui/Badge.vue";
import UiCard from "@/shared/ui/Card.vue";
import UiTabs from "@/shared/ui/Tabs.vue";

const activeTab = ref("latest");

const tabs = [
  { key: "latest", label: "最新" },
  { key: "hot", label: "热门" },
  { key: "following", label: "关注" },
  { key: "top", label: "精华" },
];
</script>

<template>
  <div class="home-grid">
    <aside class="left-rail" id="boards">
      <div class="rail-heading">
        <span>Boards</span>
        <strong>活跃版块</strong>
      </div>
      <BoardCard
        v-for="board in boards"
        :key="board.id"
        :board="board"
        @toggle-follow="() => undefined"
      />
    </aside>

    <section class="feed">
      <div class="hero">
        <UiBadge tone="green">MVP Framework</UiBadge>
        <h1>ParallelLines：让技术讨论沿着清晰的平行线生长。</h1>
        <p>
          主题流、版块治理、实时通知与深色代码块已经有了可落地的骨架。
          下一步接入真实 API 与持久化模型。
        </p>
      </div>

      <div class="feed-toolbar">
        <UiTabs v-model="activeTab" :tabs="tabs" />
      </div>

      <TopicList :topics="topics" />

      <section class="post-preview">
        <h2>楼层预览</h2>
        <PostItem :post="highlightedPost" />
      </section>
    </section>

    <aside class="right-rail">
      <ComposerDrawer />
      <UiCard class="rules-card">
        <h3>社区规则</h3>
        <ol>
          <li>讨论问题时给出上下文与已尝试方案。</li>
          <li>代码块默认深色展示，保持可复制。</li>
          <li>举报与审核保留审计日志。</li>
        </ol>
      </UiCard>
    </aside>
  </div>
</template>

<style scoped>
.home-grid {
  display: grid;
  grid-template-columns: minmax(15rem, 20rem) minmax(0, 1fr) minmax(17rem, 23rem);
  gap: 1rem;
  align-items: start;
}

.left-rail,
.right-rail,
.feed {
  display: grid;
  gap: 1rem;
}

.rail-heading {
  padding: 0.4rem 0.35rem;
}

.rail-heading span {
  color: var(--accent-geek);
  font-size: 0.78rem;
  font-weight: 850;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}

.rail-heading strong {
  display: block;
  margin-top: 0.15rem;
  color: var(--title);
  font-size: 1.1rem;
}

.hero {
  position: relative;
  overflow: hidden;
  border: 1px solid rgba(229, 231, 235, 0.95);
  border-radius: 1.5rem;
  padding: clamp(1.4rem, 4vw, 2.6rem);
  background:
    linear-gradient(135deg, rgba(59, 130, 246, 0.13), transparent 44%),
    linear-gradient(315deg, rgba(16, 185, 129, 0.14), transparent 40%),
    rgba(255, 255, 255, 0.88);
  box-shadow: var(--shadow-card);
}

.hero::after {
  position: absolute;
  right: -5rem;
  bottom: -5rem;
  width: 14rem;
  height: 14rem;
  border: 1px solid rgba(59, 130, 246, 0.18);
  border-radius: 999px;
  content: "";
}

h1 {
  max-width: 44rem;
  margin: 0.75rem 0;
  color: var(--title);
  font-size: clamp(2rem, 5vw, 4.5rem);
  line-height: 0.98;
  letter-spacing: -0.075em;
}

.hero p {
  max-width: 43rem;
  margin: 0;
  font-size: 1.05rem;
  line-height: 1.8;
}

.feed-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.post-preview {
  display: grid;
  gap: 0.8rem;
}

.post-preview h2,
.rules-card h3 {
  margin: 0;
  color: var(--title);
}

.rules-card {
  padding: 1rem;
}

.rules-card ol {
  margin: 0.75rem 0 0;
  padding-left: 1.2rem;
  line-height: 1.7;
}

@media (max-width: 1180px) {
  .home-grid {
    grid-template-columns: minmax(0, 1fr) minmax(17rem, 23rem);
  }

  .left-rail {
    grid-column: 1 / -1;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .rail-heading {
    grid-column: 1 / -1;
  }
}

@media (max-width: 880px) {
  .home-grid,
  .left-rail {
    grid-template-columns: 1fr;
  }
}
</style>
