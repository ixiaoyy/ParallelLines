<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";

import type { BoardSummary } from "@/entities/board/model";
import { boards, readRouteParam } from "@/shared/api/mockForum";
import { compactNumber } from "@/shared/lib/format";
import UiBadge from "@/shared/ui/Badge.vue";
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";

type TopicIntent = "question" | "bug" | "idea" | "guide";

type PublishState = "idle" | "saved" | "submitted";

interface NewTopicDraft {
  boardSlug: string;
  intent: TopicIntent;
  title: string;
  body: string;
  tags: string;
}

const DRAFT_STORAGE_KEY = "parallellines:new-topic-draft";

const route = useRoute();

const sectionLinks = [
  { id: "board", label: "选择版块", helper: "先找对问题区" },
  { id: "title", label: "标题", helper: "症状 + 环境" },
  { id: "content", label: "正文", helper: "日志与复现" },
  { id: "tags", label: "标签", helper: "方便检索" },
  { id: "preview", label: "预览检查", helper: "确认可回答" },
  { id: "drafts", label: "草稿", helper: "自动保存" },
];

const topicIntents: Array<{ key: TopicIntent; label: string; helper: string }> = [
  { key: "question", label: "我要排障", helper: "报错、安装、升级、登录问题" },
  { key: "bug", label: "确认缺陷", helper: "可复现路径和影响范围" },
  { key: "idea", label: "功能提案", helper: "收益、成本、备选方案" },
  { key: "guide", label: "经验复盘", helper: "沉淀步骤和结论" },
];

const defaultDraft: NewTopicDraft = {
  boardSlug: "support",
  intent: "question",
  title: "",
  body: "",
  tags: "",
};

const selectedBoardSlug = ref(defaultDraft.boardSlug);
const selectedIntent = ref<TopicIntent>(defaultDraft.intent);
const title = ref(defaultDraft.title);
const body = ref(defaultDraft.body);
const tags = ref(defaultDraft.tags);
const publishState = ref<PublishState>("idle");

const selectedBoard = computed(() => boards.find((board) => board.slug === selectedBoardSlug.value) ?? boards[0]);

const parsedTags = computed(() =>
  tags.value
    .split(/[，,]/)
    .map((tag) => tag.trim())
    .filter(Boolean)
    .slice(0, 6),
);

const checklist = computed(() => [
  { label: "已选择版块", done: Boolean(selectedBoard.value) },
  { label: "标题不少于 12 个字", done: title.value.trim().length >= 12 },
  { label: "正文包含复现/背景", done: body.value.trim().length >= 40 },
  { label: "至少 1 个标签", done: parsedTags.value.length > 0 },
]);

const completion = computed(() => checklist.value.filter((item) => item.done).length);
const canPublish = computed(() => checklist.value.every((item) => item.done));
const draftStatus = computed(() => {
  if (publishState.value === "submitted") {
    return "已生成发布预览";
  }

  if (publishState.value === "saved") {
    return "草稿已保存";
  }

  return "正在编辑";
});

const previewBody = computed(() =>
  body.value.trim() || "正文预览会显示在这里。建议包含：环境、错误信息、复现步骤、已经尝试过的方法。",
);

onMounted(() => {
  const savedDraft = readSavedDraft();
  const queryBoard = readRouteParam(route.query.board as string | string[] | undefined);

  if (savedDraft) {
    selectedBoardSlug.value = savedDraft.boardSlug;
    selectedIntent.value = savedDraft.intent;
    title.value = savedDraft.title;
    body.value = savedDraft.body;
    tags.value = savedDraft.tags;
  }

  if (boards.some((board) => board.slug === queryBoard)) {
    selectedBoardSlug.value = queryBoard;
  }
});

watch([selectedBoardSlug, selectedIntent, title, body, tags], () => {
  saveDraft();
});

function chooseBoard(board: BoardSummary) {
  selectedBoardSlug.value = board.slug;
}

function chooseIntent(intent: TopicIntent) {
  selectedIntent.value = intent;
}

function handleSaveDraft() {
  saveDraft();
  publishState.value = "saved";
}

function handleSubmit() {
  if (!canPublish.value) {
    return;
  }

  saveDraft();
  publishState.value = "submitted";
}

function saveDraft() {
  if (typeof window === "undefined") {
    return;
  }

  const draft: NewTopicDraft = {
    boardSlug: selectedBoardSlug.value,
    intent: selectedIntent.value,
    title: title.value,
    body: body.value,
    tags: tags.value,
  };

  window.localStorage.setItem(DRAFT_STORAGE_KEY, JSON.stringify(draft));
}

function readSavedDraft() {
  if (typeof window === "undefined") {
    return null;
  }

  const rawDraft = window.localStorage.getItem(DRAFT_STORAGE_KEY);

  if (!rawDraft) {
    return null;
  }

  try {
    const value: unknown = JSON.parse(rawDraft);

    if (!isDraft(value)) {
      return null;
    }

    return value;
  } catch {
    return null;
  }
}

function isDraft(value: unknown): value is NewTopicDraft {
  if (!isRecord(value)) {
    return false;
  }

  return (
    typeof value.boardSlug === "string" &&
    isTopicIntent(value.intent) &&
    typeof value.title === "string" &&
    typeof value.body === "string" &&
    typeof value.tags === "string"
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isTopicIntent(value: unknown): value is TopicIntent {
  return value === "question" || value === "bug" || value === "idea" || value === "guide";
}
</script>

<template>
  <div class="new-topic-page">
    <section class="new-topic-hero" aria-labelledby="new-topic-title">
      <div>
        <UiBadge tone="blue">发布主题</UiBadge>
        <h1 id="new-topic-title">把问题写成能被接住的主题。</h1>
        <p>这不是“随便发一条动态”的页面。先选问题场景，再补齐标题、日志、复现路径和标签。</p>
      </div>
      <dl aria-label="发帖状态">
        <div>
          <dt>完成度</dt>
          <dd>{{ completion }}/{{ checklist.length }}</dd>
        </div>
        <div>
          <dt>当前版块</dt>
          <dd>{{ selectedBoard?.name }}</dd>
        </div>
        <div>
          <dt>草稿</dt>
          <dd>{{ draftStatus }}</dd>
        </div>
      </dl>
    </section>

    <div class="new-topic-layout">
      <aside class="topic-rail" aria-label="发帖步骤导航">
        <RouterLink class="rail-back" to="/boards">← 返回版块</RouterLink>
        <a v-for="link in sectionLinks" :key="link.id" class="rail-link" :href="`#${link.id}`">
          <strong>{{ link.label }}</strong>
          <span>{{ link.helper }}</span>
        </a>
      </aside>

      <form class="topic-form" aria-label="发布主题表单" @submit.prevent="handleSubmit">
        <UiCard id="board" class="form-panel">
          <div class="panel-heading">
            <span>01</span>
            <div>
              <h2>先选择问题归属</h2>
              <p>游客和答题者都会先看版块，别让问题走错队列。</p>
            </div>
          </div>

          <div class="board-picker" role="list" aria-label="选择版块">
            <button
              v-for="board in boards"
              :key="board.id"
              type="button"
              :class="{ active: selectedBoardSlug === board.slug }"
              :style="{ '--board-color': board.color }"
              @click="chooseBoard(board)"
            >
              <span aria-hidden="true"></span>
              <strong>{{ board.name }}</strong>
              <small>{{ board.description }}</small>
              <em>{{ compactNumber(board.topicCount) }} 主题</em>
            </button>
          </div>
        </UiCard>

        <UiCard id="title" class="form-panel">
          <div class="panel-heading">
            <span>02</span>
            <div>
              <h2>标题先说清楚问题</h2>
              <p>推荐结构：症状 + 环境 + 关键对象，例如 “OIDC 组同步后本地手动组被移除”。</p>
            </div>
          </div>

          <div class="intent-picker" aria-label="主题类型">
            <button
              v-for="intent in topicIntents"
              :key="intent.key"
              type="button"
              :class="{ active: selectedIntent === intent.key }"
              @click="chooseIntent(intent.key)"
            >
              <strong>{{ intent.label }}</strong>
              <span>{{ intent.helper }}</span>
            </button>
          </div>

          <label class="field-block">
            <span>主题标题</span>
            <input v-model="title" maxlength="90" placeholder="例如：升级到 v0.1 后迁移提示缺少 notification_cursor 字段" />
          </label>
        </UiCard>

        <UiCard id="content" class="form-panel">
          <div class="panel-heading">
            <span>03</span>
            <div>
              <h2>正文补齐可复现信息</h2>
              <p>把环境、步骤、日志、预期结果分开写，别人不用反复追问。</p>
            </div>
          </div>

          <label class="field-block">
            <span>正文</span>
            <textarea
              v-model="body"
              rows="10"
              placeholder="环境：\n复现步骤：\n实际结果：\n期望结果：\n我已经尝试过："
            ></textarea>
          </label>
        </UiCard>

        <UiCard id="tags" class="form-panel">
          <div class="panel-heading">
            <span>04</span>
            <div>
              <h2>标签帮助后来者找到它</h2>
              <p>用逗号分隔，最多展示 6 个。优先写技术栈、错误对象、模块名。</p>
            </div>
          </div>

          <label class="field-block">
            <span>标签</span>
            <input v-model="tags" placeholder="例如：openid-connect, 迁移, 数据库" />
          </label>

          <div class="tag-preview" aria-label="标签预览">
            <span v-for="tag in parsedTags" :key="tag">#{{ tag }}</span>
            <em v-if="parsedTags.length === 0">还没有标签</em>
          </div>
        </UiCard>

        <UiCard id="preview" class="form-panel preview-panel">
          <div class="panel-heading">
            <span>05</span>
            <div>
              <h2>预览与发布检查</h2>
              <p>发布前先确认它是否足够清晰、可搜索、可回答。</p>
            </div>
          </div>

          <article class="topic-preview-card" :style="{ '--board-color': selectedBoard?.color }">
            <header>
              <span>{{ selectedBoard?.name }}</span>
              <strong>{{ title || "这里会显示你的主题标题" }}</strong>
            </header>
            <p>{{ previewBody }}</p>
            <footer>
              <span v-for="tag in parsedTags" :key="tag">#{{ tag }}</span>
              <em v-if="parsedTags.length === 0">#待补充标签</em>
            </footer>
          </article>

          <ul class="publish-checklist">
            <li v-for="item in checklist" :key="item.label" :class="{ done: item.done }">
              <span aria-hidden="true">{{ item.done ? "✓" : "·" }}</span>
              {{ item.label }}
            </li>
          </ul>

          <div v-if="publishState === 'submitted'" class="submit-result" role="status">
            示例环境已生成发布预览；接入后端 API 后这里会跳转到新主题详情页。
          </div>
        </UiCard>

        <UiCard id="drafts" class="form-panel draft-panel">
          <div>
            <h2>草稿保护</h2>
            <p>当前内容会自动保存在本机浏览器。你也可以手动保存，避免误关页面丢失。</p>
          </div>
          <div class="draft-actions">
            <UiButton type="button" tone="ghost" @click="handleSaveDraft">保存草稿</UiButton>
            <UiButton type="submit" tone="primary" :disabled="!canPublish">发布主题</UiButton>
          </div>
        </UiCard>
      </form>

      <aside class="topic-helper" aria-label="发帖辅助说明">
        <UiCard class="helper-card">
          <span>快速模板</span>
          <h2>排障帖最少包含</h2>
          <ol>
            <li>环境：系统、浏览器、版本、部署方式。</li>
            <li>复现：从哪个入口点到哪一步出错。</li>
            <li>日志：完整错误、请求 ID、时间点。</li>
            <li>期望：你希望它应该如何表现。</li>
          </ol>
        </UiCard>
      </aside>
    </div>
  </div>
</template>

<style scoped lang="scss" src="./NewTopicPage.scss"></style>
