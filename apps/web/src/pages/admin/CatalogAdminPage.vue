<script setup lang="ts">
import { useQuery, useQueryClient } from "@tanstack/vue-query";
import { computed, onUnmounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";

import {
  createCatalogCategory,
  createCatalogProject,
  fetchAdminCatalog,
  updateCatalogCategory,
  updateCatalogProject,
} from "@/features/catalog/adminApi";
import type {
  AdminCatalogCategory,
  AdminCatalogProject,
  CategoryDraftPayload,
  ProjectDraftPayload,
} from "@/features/catalog/adminModel";
import { fetchAdminCatalogSubmissions, fetchAdminSubmissionCover, reviewCatalogSubmission } from "@/features/catalog/submissionsApi";
import type { AdminCatalogSubmission } from "@/features/catalog/submissionsModel";
import { formatMetric, sourceNameLabel, sourceTypeLabel } from "@/features/analytics/model";
import { useLogout } from "@/features/auth/queries";
import { useAnalyticsOverview } from "@/features/analytics/queries";
import { uploadFile } from "@/features/uploads/api";
import { queryKeys } from "@/shared/api/queryKeys";
import { resolveApiAssetUrl } from "@/shared/api/client";
import UiButton from "@/shared/ui/Button.vue";

type AdminTab = "traffic" | "review" | "catalog";
type EditorKind = "category" | "project";

const activeTab = ref<AdminTab>("traffic");
const router = useRouter();
const logout = useLogout();
const queryClient = useQueryClient();
const today = new Date();
const thirtyDaysAgo = new Date(today);
thirtyDaysAgo.setDate(today.getDate() - 29);
const startDate = ref(toDateInput(thirtyDaysAgo));
const endDate = ref(toDateInput(today));
const dateRange = computed(() => ({ startDate: startDate.value, endDate: endDate.value }));
const rangeIsValid = computed(() => Boolean(startDate.value && endDate.value && startDate.value <= endDate.value));
const trafficQuery = useAnalyticsOverview(dateRange, computed(() => activeTab.value === "traffic" && rangeIsValid.value));
const catalogQuery = useQuery({
  queryKey: queryKeys.adminCatalog,
  queryFn: fetchAdminCatalog,
  enabled: computed(() => activeTab.value === "catalog"),
  retry: false,
});
const submissionsQuery = useQuery({
  queryKey: queryKeys.adminCatalogSubmissions,
  queryFn: fetchAdminCatalogSubmissions,
  enabled: computed(() => activeTab.value === "review"),
  retry: false,
});
const pendingSubmissions = computed(() =>
  submissionsQuery.data.value?.filter((submission) => submission.status === "pending") ?? [],
);
const reviewPendingId = ref("");
const reviewError = ref("");
const coverPreviewUrls = ref<Record<string, string>>({});
const coverPreviewLoadingId = ref("");
const coverPreviewErrorId = ref("");

onUnmounted(() => {
  Object.values(coverPreviewUrls.value).forEach((previewUrl) => URL.revokeObjectURL(previewUrl));
});

// 待审封面需要管理员凭据，按需读取并释放 Blob URL，避免公开直连受保护资源。
async function previewSubmissionCover(submission: AdminCatalogSubmission): Promise<void> {
  if (!submission.cover_url || coverPreviewLoadingId.value || coverPreviewUrls.value[submission.id]) return;
  coverPreviewErrorId.value = "";
  coverPreviewLoadingId.value = submission.id;
  try {
    const cover = await fetchAdminSubmissionCover(submission.id);
    coverPreviewUrls.value = { ...coverPreviewUrls.value, [submission.id]: URL.createObjectURL(cover) };
  } catch {
    coverPreviewErrorId.value = submission.id;
  } finally {
    coverPreviewLoadingId.value = "";
  }
}

const categories = computed(() => catalogQuery.data.value?.categories ?? []);
const projects = computed(() => categories.value.flatMap((category) => category.projects));
const filterCategoryId = ref("");
const filteredProjects = computed(() =>
  filterCategoryId.value
    ? projects.value.filter((project) => project.category_id === filterCategoryId.value)
    : projects.value,
);
const editorKind = ref<EditorKind | null>(null);
const editingId = ref<string | null>(null);
const categoryDraft = reactive<CategoryDraftPayload>({
  slug: "",
  name: "",
  icon_upload_id: null,
  sort_order: 0,
  is_visible: true,
});
const projectDraft = reactive<ProjectDraftPayload>({
  category_id: "",
  slug: "",
  name: "",
  url: "",
  kind: "external",
  description: null,
  author_name: null,
  icon_upload_id: null,
  sort_order: 0,
  is_visible: true,
});
const existingIconUrl = ref<string | null>(null);
const selectedIconFile = ref<File | null>(null);
const iconError = ref("");
const saveError = ref("");
const isSaving = ref(false);
const visibilityPendingKey = ref("");
const fileInput = ref<HTMLInputElement | null>(null);

const sourceRows = computed(() => trafficQuery.data.value?.traffic_sources ?? []);
const entryRows = computed(() => trafficQuery.data.value?.entry_pages ?? []);
const activeDraft = computed(() => editorKind.value === "category" ? categoryDraft : projectDraft);
const editorTitle = computed(() => {
  if (editorKind.value === "category") return editingId.value ? "编辑分类" : "新增分类";
  if (editorKind.value === "project") return editingId.value ? "编辑项目" : "新增项目";
  return "";
});

// 后台独立于旧论坛外壳，退出时清除凭据并回到公开目录。
async function leaveAdmin(): Promise<void> {
  await logout();
  await router.replace({ name: "home" });
}

// 按浏览器本地日期生成统计区间，避免 UTC 时区造成日期偏移。
function toDateInput(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

// 选择最近 N 天的访问数据；结束日期始终使用浏览器本地当天。
function selectRecentDays(days: number): void {
  const end = new Date();
  const start = new Date(end);
  start.setDate(end.getDate() - days + 1);
  startDate.value = toDateInput(start);
  endDate.value = toDateInput(end);
}

// 清理上一次编辑的上传与错误状态，不改变目录中的已保存记录。
function resetEditorState(): void {
  selectedIconFile.value = null;
  existingIconUrl.value = null;
  iconError.value = "";
  saveError.value = "";
  if (fileInput.value) fileInput.value.value = "";
}

// 开始新增分类；分类标识在创建后保持稳定，用于目录引用。
function newCategory(): void {
  resetEditorState();
  editingId.value = null;
  Object.assign(categoryDraft, {
    slug: "", name: "", icon_upload_id: null, sort_order: 0, is_visible: true,
  });
  editorKind.value = "category";
}

// 编辑已有分类，包含已隐藏的分类与当前图标。
function editCategory(category: AdminCatalogCategory): void {
  resetEditorState();
  editingId.value = category.id;
  Object.assign(categoryDraft, {
    slug: category.slug,
    name: category.name,
    icon_upload_id: category.icon_upload_id,
    sort_order: category.sort_order,
    is_visible: category.is_visible,
  });
  existingIconUrl.value = category.icon_url;
  editorKind.value = "category";
}

// 新项目仅使用 HTTPS 外链；站内游戏由现有受保护入口提供。
function newProject(): void {
  resetEditorState();
  editingId.value = null;
  Object.assign(projectDraft, {
    category_id: filterCategoryId.value || categories.value[0]?.id || "",
    slug: "", name: "", url: "", kind: "external", description: null,
    author_name: null,
    icon_upload_id: null, sort_order: 0, is_visible: true,
  });
  editorKind.value = "project";
}

// 编辑项目时保留其站内/外类型；站内地址在表单中只读。
function editProject(project: AdminCatalogProject): void {
  resetEditorState();
  editingId.value = project.id;
  Object.assign(projectDraft, {
    category_id: project.category_id,
    slug: project.slug,
    name: project.name,
    url: project.url,
    kind: project.kind,
    description: project.description,
    author_name: project.author_name,
    icon_upload_id: project.icon_upload_id,
    sort_order: project.sort_order,
    is_visible: project.is_visible,
  });
  existingIconUrl.value = project.icon_url;
  editorKind.value = "project";
}

// 只接受后台允许的四种图标格式；无效文件不进入上传流程。
function selectIcon(event: Event): void {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0] ?? null;
  iconError.value = "";
  if (!file) return;
  if (!/^image\/(png|jpeg|gif|webp)$/.test(file.type)) {
    selectedIconFile.value = null;
    input.value = "";
    iconError.value = "请上传 PNG、JPG、GIF 或 WebP 图片。";
    return;
  }
  selectedIconFile.value = file;
}

// 清除图标仅更新目录关联，不在此页面删除历史上传文件。
function clearIcon(): void {
  activeDraft.value.icon_upload_id = null;
  selectedIconFile.value = null;
  existingIconUrl.value = null;
  iconError.value = "";
  if (fileInput.value) fileInput.value.value = "";
}

// 先上传已选图标再保存目录记录；上传成功后保留 ID，便于失败重试时避免重复上传。
async function saveEditor(): Promise<void> {
  if (!editorKind.value || isSaving.value || iconError.value) return;
  const kind = editorKind.value;
  const recordId = editingId.value;
  const categoryPayload = kind === "category"
    ? { ...categoryDraft, name: categoryDraft.name.trim(), slug: categoryDraft.slug.trim() }
    : null;
  const projectPayload: ProjectDraftPayload | null = kind === "project"
    ? {
        ...projectDraft,
        name: projectDraft.name.trim(),
        slug: projectDraft.slug.trim(),
        url: projectDraft.url.trim(),
        description: projectDraft.description?.trim() || null,
        author_name: projectDraft.author_name?.trim() || null,
      }
    : null;
  saveError.value = "";
  isSaving.value = true;
  try {
    if (selectedIconFile.value) {
      const upload = await uploadFile(selectedIconFile.value, "catalog_icon");
      activeDraft.value.icon_upload_id = upload.id;
      if (categoryPayload) categoryPayload.icon_upload_id = upload.id;
      if (projectPayload) projectPayload.icon_upload_id = upload.id;
      existingIconUrl.value = upload.url;
      selectedIconFile.value = null;
      if (fileInput.value) fileInput.value.value = "";
    }
    if (categoryPayload) {
      if (recordId) await updateCatalogCategory(recordId, categoryPayload);
      else await createCatalogCategory(categoryPayload);
    } else if (projectPayload) {
      if (recordId) await updateCatalogProject(recordId, projectPayload);
      else await createCatalogProject(projectPayload);
    }
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.adminCatalog }),
      queryClient.invalidateQueries({ queryKey: queryKeys.catalog }),
    ]);
    editorKind.value = null;
    editingId.value = null;
    resetEditorState();
  } catch {
    saveError.value = "保存失败，请稍后重试。";
  } finally {
    isSaving.value = false;
  }
}

// 后台按公开状态切换，保留原有记录与评分。
async function setCategoryVisible(category: AdminCatalogCategory, isVisible: boolean): Promise<void> {
  if (visibilityPendingKey.value) return;
  saveError.value = "";
  visibilityPendingKey.value = `category:${category.id}`;
  try {
    await updateCatalogCategory(category.id, {
      slug: category.slug, name: category.name,
      icon_upload_id: category.icon_upload_id,
      sort_order: category.sort_order, is_visible: isVisible,
    });
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.adminCatalog }),
      queryClient.invalidateQueries({ queryKey: queryKeys.catalog }),
    ]);
  } catch {
    saveError.value = "保存失败，请稍后重试。";
  } finally {
    visibilityPendingKey.value = "";
  }
}

// 项目隐藏只改变公开列表状态，不删除项目与既有评分。
async function setProjectVisible(project: AdminCatalogProject, isVisible: boolean): Promise<void> {
  if (visibilityPendingKey.value) return;
  saveError.value = "";
  visibilityPendingKey.value = `project:${project.id}`;
  try {
    await updateCatalogProject(project.id, {
      category_id: project.category_id, slug: project.slug, name: project.name,
      url: project.url, kind: project.kind, description: project.description,
      author_name: project.author_name,
      icon_upload_id: project.icon_upload_id,
      sort_order: project.sort_order, is_visible: isVisible,
    });
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.adminCatalog }),
      queryClient.invalidateQueries({ queryKey: queryKeys.catalog }),
    ]);
  } catch {
    saveError.value = "保存失败，请稍后重试。";
  } finally {
    visibilityPendingKey.value = "";
  }
}

// 管理员审核待审投稿；后端写入完成后刷新投稿与目录，避免重复上线。
async function reviewSubmission(submission: AdminCatalogSubmission, decision: "approve" | "reject"): Promise<void> {
  if (reviewPendingId.value || submission.status !== "pending") return;
  reviewError.value = "";
  reviewPendingId.value = submission.id;
  try {
    await reviewCatalogSubmission(submission.id, decision);
    const previewUrl = coverPreviewUrls.value[submission.id];
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
      const nextPreviews = { ...coverPreviewUrls.value };
      delete nextPreviews[submission.id];
      coverPreviewUrls.value = nextPreviews;
    }
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.adminCatalogSubmissions }),
      queryClient.invalidateQueries({ queryKey: queryKeys.adminCatalog }),
      queryClient.invalidateQueries({ queryKey: queryKeys.catalog }),
    ]);
  } catch {
    reviewError.value = "保存失败，请稍后重试。";
  } finally {
    reviewPendingId.value = "";
  }
}
</script>

<template>
  <main class="catalog-admin">
    <header class="catalog-admin__header">
      <div>
        <p class="catalog-admin__eyebrow">平行线后台</p>
        <h1>站点管理</h1>
        <p>查看访问情况，审核投稿，维护公开目录的分类和项目。</p>
      </div>
      <div class="catalog-admin__header-actions">
        <RouterLink class="catalog-admin__visit" to="/">查看网站<span aria-hidden="true">↗</span></RouterLink>
        <button type="button" class="catalog-admin__logout" @click="leaveAdmin">退出登录</button>
      </div>
    </header>

    <nav class="catalog-admin__tabs" aria-label="后台功能">
      <button type="button" :class="{ 'is-active': activeTab === 'traffic' }" :aria-pressed="activeTab === 'traffic'" @click="activeTab = 'traffic'">流量统计</button>
      <button type="button" :class="{ 'is-active': activeTab === 'review' }" :aria-pressed="activeTab === 'review'" @click="activeTab = 'review'">投稿审核</button>
      <button type="button" :class="{ 'is-active': activeTab === 'catalog' }" :aria-pressed="activeTab === 'catalog'" @click="activeTab = 'catalog'">目录管理</button>
    </nav>

    <section v-if="activeTab === 'traffic'" class="catalog-admin__section" aria-labelledby="traffic-heading">
      <div class="catalog-admin__section-head">
        <div><h2 id="traffic-heading">流量统计</h2><p>按日期查看公开站的访问量、来源和入口页。</p></div>
        <div class="catalog-admin__presets" aria-label="常用时间范围">
          <button v-for="days in [7, 30, 90]" :key="days" type="button" @click="selectRecentDays(days)">最近 {{ days }} 天</button>
        </div>
      </div>
      <div class="catalog-admin__filters">
        <label>开始日期<input v-model="startDate" type="date" :max="endDate" required /></label>
        <label>结束日期<input v-model="endDate" type="date" :min="startDate" required /></label>
        <UiButton tone="subtle" :disabled="trafficQuery.isFetching.value || !rangeIsValid" @click="trafficQuery.refetch()">刷新</UiButton>
      </div>
      <div v-if="trafficQuery.isPending.value" class="catalog-admin__state" role="status">正在读取统计数据…</div>
      <div v-else-if="trafficQuery.isError.value" class="catalog-admin__state">
        <UiButton tone="subtle" @click="trafficQuery.refetch()">重新加载</UiButton>
      </div>
      <template v-else-if="trafficQuery.data.value">
        <dl class="catalog-admin__metrics">
          <div><dt>访问量 PV</dt><dd>{{ formatMetric(trafficQuery.data.value.totals.page_views) }}</dd></div>
          <div><dt>独立访客 UV</dt><dd>{{ formatMetric(trafficQuery.data.value.totals.unique_visitors) }}</dd></div>
          <div><dt>外部引流</dt><dd>{{ formatMetric(trafficQuery.data.value.totals.external_referrals) }}</dd></div>
        </dl>
        <div class="catalog-admin__tables">
          <section aria-labelledby="sources-heading">
            <h3 id="sources-heading">访问来源</h3>
            <div class="catalog-admin__table-scroll"><table>
              <thead><tr><th scope="col">来源</th><th scope="col">访问次数</th><th scope="col">访客</th></tr></thead>
              <tbody><tr v-for="source in sourceRows" :key="`${source.source_type}:${source.source_name}`">
                <td><strong>{{ sourceNameLabel(source.source_name) }}</strong><small>{{ sourceTypeLabel(source.source_type) }}</small></td>
                <td>{{ formatMetric(source.visit_count) }}</td><td>{{ formatMetric(source.unique_visitors) }}</td>
              </tr></tbody>
            </table></div>
            <p v-if="!sourceRows.length" class="catalog-admin__empty">当前范围内暂无访问来源。</p>
          </section>
          <section aria-labelledby="entries-heading">
            <h3 id="entries-heading">入口页面</h3>
            <div class="catalog-admin__table-scroll"><table>
              <thead><tr><th scope="col">页面</th><th scope="col">访问次数</th><th scope="col">访客</th></tr></thead>
              <tbody><tr v-for="entry in entryRows" :key="entry.path">
                <td><strong>{{ entry.title || entry.path }}</strong><small>{{ entry.path }}</small></td>
                <td>{{ formatMetric(entry.visit_count) }}</td><td>{{ formatMetric(entry.unique_visitors) }}</td>
              </tr></tbody>
            </table></div>
            <p v-if="!entryRows.length" class="catalog-admin__empty">当前范围内暂无入口页数据。</p>
          </section>
        </div>
      </template>
    </section>

    <section v-else-if="activeTab === 'review'" class="catalog-admin__section" aria-labelledby="review-heading">
      <div class="catalog-admin__section-head">
        <div><h2 id="review-heading">投稿审核</h2><p>查看游客提交的项目，审核通过后加入公开目录。</p></div>
        <UiButton tone="subtle" :disabled="submissionsQuery.isFetching.value || Boolean(reviewPendingId)" @click="submissionsQuery.refetch()">刷新</UiButton>
      </div>
      <p v-if="reviewError" class="catalog-admin__error" role="alert">{{ reviewError }}</p>
      <div v-if="submissionsQuery.isPending.value" class="catalog-admin__state" role="status">正在读取投稿…</div>
      <div v-else-if="submissionsQuery.isError.value" class="catalog-admin__state">
        <UiButton tone="subtle" @click="submissionsQuery.refetch()">重新加载</UiButton>
      </div>
      <p v-else-if="!pendingSubmissions.length" class="catalog-admin__state">暂无待审投稿。</p>
      <div v-else class="catalog-admin__submissions">
        <article v-for="submission in pendingSubmissions" :key="submission.id" class="catalog-admin__submission">
          <div class="catalog-admin__submission-head">
            <div><h3>{{ submission.project_name }}</h3><p>分类：{{ submission.category_name }}</p></div>
            <span>待审核</span>
          </div>
          <dl class="catalog-admin__submission-details">
            <div><dt>项目地址</dt><dd><a :href="submission.url" target="_blank" rel="noopener noreferrer">{{ submission.url }}</a></dd></div>
            <div v-if="submission.author_name"><dt>作者</dt><dd>{{ submission.author_name }}</dd></div>
            <div v-if="submission.contact"><dt>联系方式</dt><dd>{{ submission.contact }}</dd></div>
            <div><dt>提交时间</dt><dd>{{ new Date(submission.created_at).toLocaleString('zh-CN') }}</dd></div>
          </dl>
          <div v-if="submission.cover_url" class="catalog-admin__submission-cover">
            <button v-if="!coverPreviewUrls[submission.id]" type="button" :disabled="Boolean(coverPreviewLoadingId)" @click="previewSubmissionCover(submission)">
              {{ coverPreviewLoadingId === submission.id ? '正在读取封面…' : '查看投稿封面' }}
            </button>
            <img v-else :src="coverPreviewUrls[submission.id]" :alt="`${submission.project_name} 的投稿封面`" />
            <p v-if="coverPreviewErrorId === submission.id" role="alert">封面加载失败，请稍后重试。</p>
          </div>
          <div class="catalog-admin__submission-actions">
            <UiButton :disabled="Boolean(reviewPendingId)" :aria-label="`通过 ${submission.project_name} 的投稿`" @click="reviewSubmission(submission, 'approve')">{{ reviewPendingId === submission.id ? '处理中…' : '通过' }}</UiButton>
            <UiButton tone="danger" :disabled="Boolean(reviewPendingId)" :aria-label="`拒绝 ${submission.project_name} 的投稿`" @click="reviewSubmission(submission, 'reject')">拒绝</UiButton>
          </div>
        </article>
      </div>
    </section>

    <section v-else class="catalog-admin__section" aria-labelledby="catalog-heading">
      <div class="catalog-admin__section-head">
        <div><h2 id="catalog-heading">目录管理</h2><p>分类与项目可编辑或隐藏；评分和历史记录会保留。</p></div>
        <div class="catalog-admin__actions">
          <UiButton tone="subtle" :disabled="isSaving" @click="newCategory">新增分类</UiButton>
          <UiButton :disabled="!categories.length || isSaving" @click="newProject">新增项目</UiButton>
        </div>
      </div>
      <p class="catalog-admin__rule">最新：创建 7 天内。最热门：至少 10 人评分且平均分达到 4.5。</p>
      <div v-if="catalogQuery.isPending.value" class="catalog-admin__state" role="status">正在读取目录…</div>
      <div v-else-if="catalogQuery.isError.value" class="catalog-admin__state">
        <UiButton tone="subtle" @click="catalogQuery.refetch()">重新加载</UiButton>
      </div>
      <template v-else>
        <div class="catalog-admin__workspace">
          <div class="catalog-admin__lists">
            <section class="catalog-admin__list" aria-labelledby="categories-heading">
              <div class="catalog-admin__list-head"><h3 id="categories-heading">分类</h3><span>{{ categories.length }}</span></div>
              <p v-if="!categories.length" class="catalog-admin__empty">暂无分类。</p>
              <div v-for="category in categories" :key="category.id" class="catalog-admin__row">
                <img v-if="category.icon_url" :src="resolveApiAssetUrl(category.icon_url)" alt="" />
                <span v-else class="catalog-admin__icon-fallback" aria-hidden="true">#</span>
                <div class="catalog-admin__row-main"><strong>{{ category.name }}</strong><small>{{ category.slug }} · {{ category.projects.length }} 个项目</small></div>
                <span v-if="!category.is_visible" class="catalog-admin__hidden">已隐藏</span>
                <div class="catalog-admin__row-actions">
                  <button type="button" :disabled="isSaving" @click="editCategory(category)">编辑</button>
                  <button type="button" :disabled="Boolean(visibilityPendingKey)" @click="setCategoryVisible(category, !category.is_visible)">{{ category.is_visible ? '隐藏' : '显示' }}</button>
                </div>
              </div>
            </section>
            <section class="catalog-admin__list" aria-labelledby="projects-heading">
              <div class="catalog-admin__list-head"><h3 id="projects-heading">项目</h3><span>{{ projects.length }}</span></div>
              <label class="catalog-admin__filter">按分类查看
                <select v-model="filterCategoryId"><option value="">全部分类</option><option v-for="category in categories" :key="category.id" :value="category.id">{{ category.name }}</option></select>
              </label>
              <p v-if="!filteredProjects.length" class="catalog-admin__empty">当前分类暂无项目。</p>
              <div v-for="project in filteredProjects" :key="project.id" class="catalog-admin__row">
                <img v-if="project.icon_url" :src="resolveApiAssetUrl(project.icon_url)" alt="" />
                <span v-else class="catalog-admin__icon-fallback" aria-hidden="true">↗</span>
                <div class="catalog-admin__row-main"><strong>{{ project.name }}</strong><small>{{ categories.find((item) => item.id === project.category_id)?.name }}<span v-if="project.author_name"> · 作者：{{ project.author_name }}</span> · {{ project.rating_count }} 人评分<span v-if="project.average_score !== null"> · {{ project.average_score.toFixed(1) }} 分</span></small></div>
                <span v-if="!project.is_visible" class="catalog-admin__hidden">已隐藏</span>
                <div class="catalog-admin__row-actions">
                  <button type="button" :disabled="isSaving" @click="editProject(project)">编辑</button>
                  <button type="button" :disabled="Boolean(visibilityPendingKey)" @click="setProjectVisible(project, !project.is_visible)">{{ project.is_visible ? '隐藏' : '显示' }}</button>
                </div>
              </div>
            </section>
            <p v-if="saveError && !editorKind" class="catalog-admin__error" role="alert">{{ saveError }}</p>
          </div>

          <section v-if="editorKind" class="catalog-admin__editor" aria-labelledby="editor-heading">
            <div class="catalog-admin__editor-head"><h3 id="editor-heading">{{ editorTitle }}</h3><button type="button" aria-label="关闭编辑" :disabled="isSaving" @click="editorKind = null">×</button></div>
            <form @submit.prevent="saveEditor">
              <label>名称<input v-if="editorKind === 'category'" v-model="categoryDraft.name" type="text" maxlength="120" required /><input v-else v-model="projectDraft.name" type="text" maxlength="120" required /></label>
              <label>固定标识<input v-if="editorKind === 'category'" v-model="categoryDraft.slug" type="text" pattern="[a-z0-9]+(-[a-z0-9]+)*" maxlength="80" required :readonly="Boolean(editingId)" /><input v-else v-model="projectDraft.slug" type="text" pattern="[a-z0-9]+(-[a-z0-9]+)*" maxlength="80" required :readonly="Boolean(editingId)" /></label>
              <template v-if="editorKind === 'project'">
                <label>所属分类<select v-model="projectDraft.category_id" required><option value="" disabled>选择分类</option><option v-for="category in categories" :key="category.id" :value="category.id">{{ category.name }}</option></select></label>
                <label>项目地址<input v-model="projectDraft.url" :type="projectDraft.kind === 'external' ? 'url' : 'text'" :pattern="projectDraft.kind === 'external' ? 'https://.+' : undefined" required :readonly="projectDraft.kind === 'internal'" /></label>
                <label>作者（可选）<input v-model="projectDraft.author_name" type="text" maxlength="120" /></label>
                <label>简介（可选）<textarea v-model="projectDraft.description" maxlength="300" rows="3"></textarea></label>
              </template>
              <label>排序<input v-if="editorKind === 'category'" v-model.number="categoryDraft.sort_order" type="number" min="0" step="1" required /><input v-else v-model.number="projectDraft.sort_order" type="number" min="0" step="1" required /></label>
              <div class="catalog-admin__icon-field">
                <label for="catalog-icon-upload">图标（可选）</label>
                <div class="catalog-admin__icon-controls"><img v-if="existingIconUrl" :src="resolveApiAssetUrl(existingIconUrl)" alt="当前图标" /><input id="catalog-icon-upload" ref="fileInput" type="file" accept="image/png,image/jpeg,image/gif,image/webp" @change="selectIcon" /><button v-if="existingIconUrl || selectedIconFile" type="button" @click="clearIcon">清除图标</button></div>
                <p v-if="iconError" class="catalog-admin__error" role="alert">{{ iconError }}</p>
              </div>
              <label class="catalog-admin__check"><input v-if="editorKind === 'category'" v-model="categoryDraft.is_visible" type="checkbox" /><input v-else v-model="projectDraft.is_visible" type="checkbox" />公开显示</label>
              <p v-if="saveError" class="catalog-admin__error" role="alert">{{ saveError }}</p>
              <div class="catalog-admin__form-actions"><UiButton type="submit" :disabled="isSaving || Boolean(iconError)">{{ isSaving ? '保存中…' : '保存' }}</UiButton><UiButton tone="ghost" :disabled="isSaving" @click="editorKind = null">取消</UiButton></div>
            </form>
          </section>
        </div>
      </template>
    </section>
  </main>
</template>

<style scoped lang="scss" src="./CatalogAdminPage.scss"></style>
