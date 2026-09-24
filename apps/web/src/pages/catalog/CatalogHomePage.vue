<script setup lang="ts">
import {
  ArrowRightOutlined,
  ClockCircleFilled,
  FireFilled,
  HeartFilled,
  HeartOutlined,
  SearchOutlined,
} from "@ant-design/icons-vue";
import { computed, ref } from "vue";

import type { CatalogProject } from "@/features/catalog/model";
import { useCatalog, useRateCatalogProject } from "@/features/catalog/queries";

type SortMode = "latest" | "hot";
type CatalogEntry = CatalogProject & { categoryName: string; categorySlug: string };

const catalogQuery = useCatalog();
const ratingMutation = useRateCatalogProject();
const search = ref("");
const selectedCategory = ref("all");
const sortMode = ref<SortMode>("latest");
const pendingProjectId = ref<string | null>(null);
const ratingErrorProjectId = ref<string | null>(null);

const categories = computed(() => catalogQuery.data.value ?? []);
const allProjects = computed<CatalogEntry[]>(() =>
  categories.value.flatMap((category) =>
    category.projects.map((project) => ({
      ...project,
      categoryName: category.name,
      categorySlug: category.slug,
    })),
  ),
);
const normalizedSearch = computed(() => search.value.trim().toLocaleLowerCase());

// 按所选分类、查询词和排序模式生成公开项目列表；不改变后台配置的项目归属。
const visibleProjects = computed(() => {
  const matching = allProjects.value.filter((project) => {
    if (selectedCategory.value !== "all" && project.categorySlug !== selectedCategory.value) {
      return false;
    }
    if (!normalizedSearch.value) return true;
    return [project.name, project.description ?? "", project.host]
      .some((value) => value.toLocaleLowerCase().includes(normalizedSearch.value));
  });
  return matching.sort((left, right) => {
    if (sortMode.value === "hot") {
      const qualified = Number(isHot(right)) - Number(isHot(left));
      if (qualified) return qualified;
      const ratings = right.ratingCount - left.ratingCount;
      if (ratings) return ratings;
      const average = (right.averageScore ?? 0) - (left.averageScore ?? 0);
      if (average) return average;
    }
    // 创建时间相同时沿用后台返回顺序，避免首批导入项目被名称重新打乱。
    return Date.parse(right.createdAt) - Date.parse(left.createdAt);
  });
});

// 根据项目创建时间判断 7 天内的新标识；无效或未来时间返回 false。
function isNew(project: CatalogProject): boolean {
  const elapsed = Date.now() - Date.parse(project.createdAt);
  return Number.isFinite(elapsed) && elapsed >= 0 && elapsed <= 7 * 24 * 60 * 60 * 1000;
}

// 判断热门标识；至少 10 人且原始平均分达到 4.5，展示时的四舍五入不参与判断。
function isHot(project: CatalogProject): boolean {
  return project.ratingCount >= 10 && (project.averageScore ?? 0) >= 4.5;
}

function isFilled(project: CatalogProject, score: number): boolean {
  return score <= (project.myScore ?? 0);
}

// 提交访客首次评分；已评分或待提交时不重复发送，失败只显示已批准的错误文案。
async function rateProject(project: CatalogProject, score: number): Promise<void> {
  if (project.myScore !== null || pendingProjectId.value !== null) return;
  ratingErrorProjectId.value = null;
  pendingProjectId.value = project.id;
  try {
    await ratingMutation.mutateAsync({ projectId: project.id, score });
  } catch {
    ratingErrorProjectId.value = project.id;
  } finally {
    pendingProjectId.value = null;
  }
}
</script>

<template>
  <main class="catalog-page" aria-labelledby="catalog-title">
    <div class="catalog-page__wrap">
      <header class="catalog-header">
        <RouterLink class="catalog-brand" to="/" aria-label="平行线首页">
          <img src="/logo-lines-mark.png" alt="" width="44" height="44" />
          <span>平行线</span>
        </RouterLink>
        <span class="catalog-header__label">项目目录</span>
      </header>

      <section class="catalog-hero" aria-labelledby="catalog-title">
        <div class="catalog-hero__copy">
          <p class="catalog-hero__eyebrow">平行线 · 发现有趣项目</p>
          <h1 id="catalog-title">今天想玩点什么？</h1>
          <p class="catalog-hero__intro">按分类浏览，或搜索喜欢的项目，点开卡片即可开始。</p>
          <label class="catalog-search">
            <SearchOutlined class="catalog-search__icon" aria-hidden="true" />
            <span class="catalog-search__sr">搜索项目名称、介绍或网址</span>
            <input
              v-model="search"
              type="search"
              placeholder="搜项目名称、介绍或网址"
              autocomplete="off"
            />
          </label>
        </div>
        <div class="catalog-hero__art" aria-hidden="true">
          <span class="catalog-hero__orbit catalog-hero__orbit--one"></span>
          <span class="catalog-hero__orbit catalog-hero__orbit--two"></span>
          <span class="catalog-hero__spark catalog-hero__spark--one">✦</span>
          <span class="catalog-hero__spark catalog-hero__spark--two">✦</span>
          <span class="catalog-hero__spark catalog-hero__spark--three">✦</span>
          <span class="catalog-hero__disc"></span>
          <img class="catalog-hero__mascot" src="/catalog/chibi-cat-explorer.webp" alt="" width="512" height="512" />
        </div>
      </section>

      <section class="catalog-list" aria-labelledby="catalog-list-title">
        <div class="catalog-list__heading">
          <div>
            <h2 id="catalog-list-title">项目一览</h2>
            <p>选一个感兴趣的项目，去看看吧。</p>
          </div>
          <span v-if="!catalogQuery.isLoading.value && !catalogQuery.isError.value" class="catalog-list__count">
            {{ visibleProjects.length }} 个项目
          </span>
        </div>

        <template v-if="catalogQuery.isLoading.value">
          <div class="catalog-state catalog-state--loading" role="status" aria-label="正在加载项目目录">
            <span class="catalog-state__spinner" aria-hidden="true"></span>
            <span>正在加载项目目录…</span>
          </div>
        </template>
        <div v-else-if="catalogQuery.isError.value" class="catalog-state" role="alert">
          <span>项目目录暂时不可用，请稍后重试。</span>
          <button type="button" class="catalog-state__retry" @click="catalogQuery.refetch()">
            重新加载
          </button>
        </div>
        <template v-else>
          <div class="catalog-controls">
            <div class="catalog-categories" role="group" aria-label="项目分类">
              <button
                type="button"
                class="catalog-filter"
                :class="{ 'is-active': selectedCategory === 'all' }"
                :aria-pressed="selectedCategory === 'all'"
                @click="selectedCategory = 'all'"
              >
                全部
              </button>
              <button
                v-for="category in categories"
                :key="category.id"
                type="button"
                class="catalog-filter"
                :class="{ 'is-active': selectedCategory === category.slug }"
                :aria-pressed="selectedCategory === category.slug"
                @click="selectedCategory = category.slug"
              >
                <img v-if="category.iconUrl" :src="category.iconUrl" alt="" width="20" height="20" />
                {{ category.name }}
              </button>
            </div>
            <div class="catalog-sort" role="group" aria-label="项目排序">
              <button
                type="button"
                :class="{ 'is-active': sortMode === 'latest' }"
                :aria-pressed="sortMode === 'latest'"
                @click="sortMode = 'latest'"
              >最新</button>
              <button
                type="button"
                :class="{ 'is-active': sortMode === 'hot' }"
                :aria-pressed="sortMode === 'hot'"
                @click="sortMode = 'hot'"
              >最热门</button>
            </div>
          </div>

          <div v-if="visibleProjects.length === 0" class="catalog-state" role="status">
            <span>没有找到匹配的项目</span>
            <button v-if="search || selectedCategory !== 'all'" type="button" @click="search = ''; selectedCategory = 'all'">
              清除筛选
            </button>
          </div>
          <div v-else class="catalog-grid">
            <article
              v-for="(project, index) in visibleProjects"
              :key="project.id"
              class="catalog-card"
              :class="`catalog-card--tone-${index % 4}`"
            >
              <div class="catalog-card__top">
                <span class="catalog-card__icon" aria-hidden="true">
                  <img v-if="project.iconUrl" :src="project.iconUrl" alt="" width="64" height="64" />
                  <span v-else>{{ project.name.slice(0, 1) }}</span>
                </span>
                <div class="catalog-card__badges">
                  <span v-if="isNew(project)" class="catalog-card__badge catalog-card__badge--new" role="img" aria-label="新项目" title="新项目">
                    <ClockCircleFilled aria-hidden="true" />
                  </span>
                  <span v-if="isHot(project)" class="catalog-card__badge catalog-card__badge--hot" role="img" aria-label="热门项目" title="热门项目">
                    <FireFilled aria-hidden="true" />
                  </span>
                </div>
              </div>
              <div class="catalog-card__body">
                <span class="catalog-card__category">{{ project.categoryName }}</span>
                <h3>
                  <RouterLink v-if="project.kind === 'internal'" class="catalog-card__link" :to="project.url">
                    {{ project.name }}
                    <ArrowRightOutlined aria-hidden="true" />
                  </RouterLink>
                  <a v-else class="catalog-card__link" :href="project.url" target="_blank" rel="noopener noreferrer">
                    {{ project.name }}
                    <ArrowRightOutlined aria-hidden="true" />
                  </a>
                </h3>
                <p v-if="project.description" class="catalog-card__description">{{ project.description }}</p>
                <p class="catalog-card__host">{{ project.kind === 'internal' ? '站内项目' : project.host }}</p>
              </div>
              <div class="catalog-card__rating" :class="{ 'is-pending': pendingProjectId === project.id }">
                <div class="catalog-card__score">
                  <strong>{{ project.averageScore === null ? '—' : project.averageScore.toFixed(1) }}</strong>
                  <span>{{ project.ratingCount }} 人评分</span>
                </div>
                <div class="catalog-card__hearts" role="group" :aria-label="`${project.name}的评分`">
                  <button
                    v-for="score in 5"
                    :key="score"
                    type="button"
                    :disabled="project.myScore !== null || pendingProjectId !== null"
                    :aria-label="project.myScore === null ? `给${project.name}评${score}分` : `${project.name}已评${project.myScore}分，不能修改`"
                    :title="project.myScore === null ? `评${score}分` : `已评${project.myScore}分`"
                    @click="rateProject(project, score)"
                  >
                    <HeartFilled v-if="isFilled(project, score)" aria-hidden="true" />
                    <HeartOutlined v-else aria-hidden="true" />
                  </button>
                </div>
                <p v-if="ratingErrorProjectId === project.id" class="catalog-card__rating-error" role="alert">
                  评分暂时不可用，请稍后重试。
                </p>
              </div>
            </article>
          </div>
          <p class="catalog-list__rating-note">评分提交后不可修改。</p>
        </template>
      </section>
      <footer class="catalog-footer">平行线 · 发现有趣的项目</footer>
    </div>
  </main>
</template>

<style scoped lang="scss" src="./CatalogHomePage.scss"></style>
