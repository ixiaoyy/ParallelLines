<script setup lang="ts">
import { computed, ref } from "vue";
import { ArrowRightOutlined, SearchOutlined, ToolOutlined } from "@ant-design/icons-vue";

import UiButton from "@/shared/ui/Button.vue";
import SiteNavigation from "@/shared/ui/SiteNavigation.vue";

type ToolCategory = "office" | "creation";
interface ToolEntry {
  id: string;
  title: string;
  description: string;
  category: ToolCategory;
  detail: string;
  tags: string[];
  routeName: "tool-excel-formulas" | "tool-bead-pattern";
  previewKind: "excel" | "bead";
}

// 聚合页只登记已可使用的独立工具，筛选不加载教程或制图工作区。
const tools: ToolEntry[] = [
  {
    id: "excel",
    title: "Excel 公式速查",
    description: "文职常用公式，按步骤照着做。",
    category: "office",
    detail: "50 篇完整教程",
    tags: ["金额汇总", "人员匹配", "名单核对", "数据清理"],
    routeName: "tool-excel-formulas",
    previewKind: "excel",
  },
  {
    id: "bead",
    title: "拼豆图纸生成器",
    description: "将图片转换为拼豆图纸，查看色号和用量。",
    category: "creation",
    detail: "本地图片处理",
    tags: ["图片转换", "手动改格", "用量统计", "图纸导出"],
    routeName: "tool-bead-pattern",
    previewKind: "bead",
  },
];
const categories: Array<{ value: "all" | ToolCategory; label: string }> = [
  { value: "all", label: "全部" },
  { value: "office", label: "办公" },
  { value: "creation", label: "创作" },
];
const categoryLabels: Record<ToolCategory, string> = { office: "办公", creation: "创作" };
const query = ref("");
const category = ref<"all" | ToolCategory>("all");
const searchTerms = computed(() => query.value.normalize("NFKC").trim().toLocaleLowerCase().split(/\s+/).filter(Boolean));
const hasFilters = computed(() => searchTerms.value.length > 0 || category.value !== "all");

// 名称、介绍及用途标签共同参与即时搜索；多个词与分类同时满足才显示。
const visibleTools = computed(() => tools.filter((tool) => {
  if (category.value !== "all" && category.value !== tool.category) return false;
  const text = [tool.title, tool.description, tool.detail, categoryLabels[tool.category], ...tool.tags]
    .join(" ").normalize("NFKC").toLocaleLowerCase();
  return searchTerms.value.every((term) => text.includes(term));
}));

/** 清除搜索与分类条件，恢复全部已收录工具；不改变独立工具内的状态。 */
function clearFilters(): void {
  query.value = "";
  category.value = "all";
}
</script>

<template>
  <div class="tools-shell">
    <header class="tools-site-header">
      <RouterLink class="tools-site-brand" :to="{ name: 'home' }" aria-label="平行线首页">
        <img src="/logo-lines-mark.png" alt="" width="48" height="42" />
        <strong>平行线</strong>
      </RouterLink>
    </header>
    <main class="tools-page" aria-labelledby="tools-page-title">
      <header class="tools-page__header">
        <div class="tools-page__intro">
          <h1 id="tools-page-title"><ToolOutlined aria-hidden="true" /> 工具</h1>
          <p>按用途查找工具，打开即可使用。</p>
        </div>
        <form class="tools-search" role="search" @submit.prevent>
          <label class="tools-search__label" for="tools-query">搜索工具名称或用途</label>
          <SearchOutlined aria-hidden="true" />
          <input id="tools-query" v-model="query" type="search" aria-label="搜索工具名称或用途" placeholder="搜索工具名称或用途" autocomplete="off" />
        </form>
      </header>
      <div class="tools-toolbar">
        <div class="tools-categories" role="group" aria-label="工具分类">
          <button v-for="item in categories" :key="item.value" type="button" :aria-pressed="category === item.value" @click="category = item.value">{{ item.label }}</button>
        </div>
        <div class="tools-toolbar__results">
          <span class="tools-results" role="status" aria-live="polite">{{ visibleTools.length }} 个工具</span>
          <UiButton v-if="hasFilters && visibleTools.length" tone="ghost" @click="clearFilters">清除筛选</UiButton>
        </div>
      </div>
      <section v-if="visibleTools.length" class="tools-grid" aria-label="工具列表">
        <article v-for="tool in visibleTools" :key="tool.id" class="tools-tool" :class="`tools-tool--${tool.previewKind}`" :aria-labelledby="`${tool.id}-tool-title`">
          <div class="tools-tool__preview" aria-hidden="true">
            <div v-if="tool.previewKind === 'excel'" class="tools-excel-preview">
              <div class="tools-tool__formula"><span>fx</span> =SUMIFS(B2:B3,A2:A3,"张三")</div>
              <div class="tools-tool__sheet">
                <span></span><span>A</span><span>B</span>
                <span>1</span><strong>姓名</strong><strong>金额</strong>
                <span>2</span><span>张三</span><span>100</span>
                <span>3</span><span>张三</span><span>150</span>
                <span>4</span><strong>合计</strong><strong class="tools-tool__answer">250</strong>
              </div>
            </div>
            <div v-else class="tools-bead-preview"><img src="/tools/bead-pattern/pixel-example.svg" alt="" width="160" height="160" /><span>一格，一颗豆</span></div>
          </div>
          <div class="tools-tool__content">
            <div class="tools-tool__meta"><span class="tools-tool__category">{{ categoryLabels[tool.category] }}</span><span>{{ tool.detail }}</span></div>
            <h2 :id="`${tool.id}-tool-title`"><RouterLink :to="{ name: tool.routeName }">{{ tool.title }}</RouterLink></h2>
            <p>{{ tool.description }}</p>
            <ul class="tools-tool__topics" :aria-label="`${tool.title}用途`"><li v-for="tag in tool.tags" :key="tag">{{ tag }}</li></ul>
            <RouterLink class="tools-tool__launch" :to="{ name: tool.routeName }">打开工具 <ArrowRightOutlined aria-hidden="true" /></RouterLink>
          </div>
        </article>
      </section>
      <section v-else class="tools-empty" role="status" aria-labelledby="tools-empty-title">
        <SearchOutlined aria-hidden="true" />
        <h2 id="tools-empty-title">没有找到匹配的工具。</h2>
        <p>试试其他关键词，或清除筛选查看全部工具。</p>
        <UiButton @click="clearFilters">清除筛选</UiButton>
      </section>
    </main>
    <footer class="tools-site-footer"><SiteNavigation /></footer>
  </div>
</template>

<style scoped lang="scss" src="./ToolsPage.scss"></style>
