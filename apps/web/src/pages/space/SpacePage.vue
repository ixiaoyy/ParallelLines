<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import { message } from "ant-design-vue";

import { useCurrentUser } from "@/features/auth/queries";
import { setUserRelationship } from "@/features/social/api";
import { useUserRelationshipUsers } from "@/features/social/queries";
import SpaceJournalCard from "@/features/space/components/SpaceJournalCard.vue";
import SpaceLedgerPanel from "@/features/space/components/SpaceLedgerPanel.vue";
import SpaceMoodCalendarCard from "@/features/space/components/SpaceMoodCalendarCard.vue";
import SpaceSettingsDrawer from "@/features/space/components/SpaceSettingsDrawer.vue";
import { getPendingLocalSpaceSummary, type LocalSpacePendingSummary } from "@/features/space/api";
import {
  currentMonthString,
  formatCentsToYuan,
  getLedgerCategoryMeta,
  getMoodMeta,
  JOURNAL_CARD_THEMES,
  JOURNAL_MOODS,
  JOURNAL_WEATHERS,
  LEDGER_CATEGORIES,
  LEDGER_PAYMENT_METHODS,
  todayDateString,
  type JournalCardTheme,
  type JournalMood,
  type JournalVisibility,
  type JournalWeather,
  type LedgerCategory,
  type LedgerKind,
  type LedgerPaymentMethod,
  type SpaceChecklistItem,
  type SpaceCoverPreset,
  type SpaceJournalItem,
  type SpaceLedgerItem,
} from "@/features/space/model";
import {
  useCreateSpaceJournal,
  useCreateSpaceLedgerEntry,
  useDeleteSpaceJournal,
  useDeleteSpaceLedgerEntry,
  useLikeSpaceJournal,
  useMySpaceWorkspace,
  usePublicSpaceFeed,
  useSyncLocalSpaceToCloud,
  useUpdateSpaceJournal,
  useUpdateSpaceSettings,
} from "@/features/space/queries";
import { uploadFile } from "@/features/uploads/api";
import { hasAccessToken, resolveApiAssetUrl } from "@/shared/api/client";
import { queryClient } from "@/shared/api/queryClient";
import { queryKeys } from "@/shared/api/queryKeys";
import UiAvatar from "@/shared/ui/Avatar.vue";
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";

type SpaceMainTab = "journals" | "ledger" | "community";
type ComposerMode = "journal" | "ledger";

const currentUserQuery = useCurrentUser();
const currentUser = computed(() => currentUserQuery.data.value);
const isLoggedIn = computed(() => Boolean(currentUser.value || hasAccessToken()));
const workspaceAuthScope = computed(() =>
  currentUser.value?.id ? `user:${currentUser.value.id}` : hasAccessToken() ? "token" : "guest",
);

const selectedMonth = ref(currentMonthString());
const activeTab = ref<SpaceMainTab>("journals");
const composerMode = ref<ComposerMode>("journal");
const composerRef = ref<HTMLElement | null>(null);
const imageInputRef = ref<HTMLInputElement | null>(null);
const uploadingImage = ref(false);
const settingsOpen = ref(false);
const mobileCalendarExpanded = ref(false);

// Filters for My Journals
const filterDate = ref("");
const filterMood = ref<string>("");
const filterTag = ref("");
const filterKeyword = ref("");
const filterVisibility = ref<"all" | "public" | "private">("all");
const communityScope = ref<"all" | "following">("all");
const followBusyUsername = ref<string | null>(null);

const workspaceQuery = useMySpaceWorkspace(selectedMonth, workspaceAuthScope);
const communityFeedQuery = usePublicSpaceFeed(
  30,
  computed(() => activeTab.value === "community"),
);
const followingUsersQuery = useUserRelationshipUsers(
  computed(() => currentUser.value?.username ?? ""),
  "following",
  computed(() => activeTab.value === "community" && Boolean(currentUser.value?.username)),
);

const followingUsernames = computed(() => {
  const set = new Set<string>();
  for (const item of followingUsersQuery.data.value ?? []) {
    set.add(item.username);
  }
  return set;
});

const visibleCommunityFeed = computed(() => {
  const list = communityFeedQuery.data.value ?? [];
  if (communityScope.value === "following") {
    return list.filter(
      (item) => item.author?.username && followingUsernames.value.has(item.author.username),
    );
  }
  return list;
});

async function handleToggleFollowAuthor(entry: SpaceJournalItem) {
  const username = entry.author?.username;
  if (!username || !currentUser.value) {
    message.info("请先登录后再关注圈友");
    return;
  }
  const currentlyFollowing = followingUsernames.value.has(username);
  followBusyUsername.value = username;
  try {
    await setUserRelationship(username, "follow", !currentlyFollowing);
    void queryClient.invalidateQueries({ queryKey: queryKeys.userRelationshipUsersRoot });
    message.success(currentlyFollowing ? `已取消关注 @${username}` : `已关注 @${username}`);
  } catch {
    message.error("关注操作失败，请稍后重试");
  } finally {
    followBusyUsername.value = null;
  }
}

const createJournalMutation = useCreateSpaceJournal();
const updateJournalMutation = useUpdateSpaceJournal();
const deleteJournalMutation = useDeleteSpaceJournal();
const likeJournalMutation = useLikeSpaceJournal();
const createLedgerMutation = useCreateSpaceLedgerEntry();
const deleteLedgerMutation = useDeleteSpaceLedgerEntry();
const updateSettingsMutation = useUpdateSpaceSettings();
const syncLocalMutation = useSyncLocalSpaceToCloud();

const pendingLocalSummary = ref<LocalSpacePendingSummary>(getPendingLocalSpaceSummary());
const localSyncBannerDismissed = ref(false);

watch(isLoggedIn, (loggedIn) => {
  if (loggedIn) {
    pendingLocalSummary.value = getPendingLocalSpaceSummary();
  }
});

async function handleSyncLocalToCloud() {
  try {
    const result = await syncLocalMutation.mutateAsync();
    pendingLocalSummary.value = getPendingLocalSpaceSummary();
    message.success(
      `已同步 ${result.journalsSynced} 篇手账和 ${result.ledgersSynced} 笔账单到云端`,
    );
  } catch {
    message.error("同步本地记录失败，请稍后重试");
  }
}

// Journal Composer State
const journalDraft = reactive({
  entry_date: todayDateString(),
  title: "",
  content: "",
  mood: "happy" as JournalMood,
  weather: "sunny" as JournalWeather,
  location: "",
  visibility: "public" as JournalVisibility,
  is_pinned: false,
  card_theme: "paper" as JournalCardTheme,
  tagInput: "",
  tags: ["日常"] as string[],
  media_urls: [] as string[],
  checklist: [] as SpaceChecklistItem[],
  newCheckItem: "",
  showTools: false,
});

// Ledger Composer State
const ledgerDraft = reactive({
  entry_date: todayDateString(),
  kind: "expense" as LedgerKind,
  amountYuan: "",
  category: "dining" as LedgerCategory,
  payment_method: "wechat" as LedgerPaymentMethod,
  note: "",
  syncToJournal: false,
  journalVisibility: "private" as JournalVisibility,
});

// Space Settings Modal State
const settingsDraft = reactive({
  space_title: "",
  space_subtitle: "",
  cover_preset: "aurora" as SpaceCoverPreset,
  monthlyBudgetYuan: "3000",
});

const workspace = computed(() => workspaceQuery.data.value);
const myJournals = computed(() => workspace.value?.journals ?? []);
const myLedgers = computed(() => workspace.value?.ledger_entries ?? []);
const ledgerSummary = computed(() => workspace.value?.ledger_summary);
const spaceSettings = computed(() => workspace.value?.settings);

watch(
  spaceSettings,
  (next) => {
    if (!next) return;
    settingsDraft.space_title = next.space_title || "";
    settingsDraft.space_subtitle = next.space_subtitle || "";
    settingsDraft.cover_preset = (next.cover_preset as SpaceCoverPreset) || "aurora";
    settingsDraft.monthlyBudgetYuan = String(
      Math.round((next.monthly_budget_cents || 300000) / 100),
    );
  },
  { immediate: true },
);

const displaySpaceTitle = computed(() => {
  if (spaceSettings.value?.space_title?.trim()) {
    return spaceSettings.value.space_title.trim();
  }
  const name =
    currentUser.value?.display_name?.trim() || currentUser.value?.username || "我";
  return `${name} 的手账空间`;
});

const displaySpaceSubtitle = computed(() => {
  if (spaceSettings.value?.space_subtitle?.trim()) {
    return spaceSettings.value.space_subtitle.trim();
  }
  return "把日常闪念、心情贴纸与每一笔生活开支，装进属于自己的安静角落。";
});

const activeCoverPreset = computed<SpaceCoverPreset>(
  () => (spaceSettings.value?.cover_preset as SpaceCoverPreset) || "aurora",
);

const recordedDaysCount = computed(() => {
  const days = new Set<string>();
  for (const item of myJournals.value) days.add(item.entry_date);
  for (const item of myLedgers.value) days.add(item.entry_date);
  return days.size;
});

const publicJournalsCount = computed(
  () => myJournals.value.filter((item) => item.visibility === "public").length,
);

const filteredJournals = computed(() => {
  const kw = filterKeyword.value.trim().toLowerCase();
  return myJournals.value.filter((item) => {
    if (filterDate.value && item.entry_date !== filterDate.value) return false;
    if (filterMood.value && item.mood !== filterMood.value) return false;
    if (filterTag.value && !item.tags?.includes(filterTag.value)) return false;
    if (filterVisibility.value !== "all" && item.visibility !== filterVisibility.value) {
      return false;
    }
    if (kw) {
      const hay = `${item.title} ${item.content} ${item.location} ${(item.tags ?? []).join(" ")}`.toLowerCase();
      if (!hay.includes(kw)) return false;
    }
    return true;
  });
});

const hasActiveJournalFilters = computed(() =>
  Boolean(
    filterDate.value ||
      filterMood.value ||
      filterTag.value ||
      filterKeyword.value.trim() ||
      filterVisibility.value !== "all",
  ),
);

function clearJournalFilters() {
  filterDate.value = "";
  filterMood.value = "";
  filterTag.value = "";
  filterKeyword.value = "";
  filterVisibility.value = "all";
}

const tagCloud = computed(() => {
  const counts = new Map<string, number>();
  for (const item of myJournals.value) {
    for (const tag of item.tags ?? []) {
      counts.set(tag, (counts.get(tag) ?? 0) + 1);
    }
  }
  return Array.from(counts.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 14);
});

function shiftMonth(delta: number) {
  const [yStr, mStr] = selectedMonth.value.split("-");
  const date = new Date(Number(yStr), Number(mStr) - 1 + delta, 1);
  const nextY = date.getFullYear();
  const nextM = String(date.getMonth() + 1).padStart(2, "0");
  selectedMonth.value = `${nextY}-${nextM}`;
  filterDate.value = "";
}

const budgetUsagePercent = computed(() => {
  const summary = ledgerSummary.value;
  if (!summary || summary.monthly_budget_cents <= 0) return 0;
  return Math.min(
    100,
    Math.round((summary.total_expense_cents * 100) / summary.monthly_budget_cents),
  );
});

const remainingBudgetCents = computed(() => {
  const summary = ledgerSummary.value;
  if (!summary) return 0;
  return summary.monthly_budget_cents - summary.total_expense_cents;
});

// Composer helpers
function addTagFromInput() {
  const raw = journalDraft.tagInput.trim().replace(/^#+/, "").trim();
  journalDraft.tagInput = "";
  if (!raw) return;
  if (!journalDraft.tags.includes(raw) && journalDraft.tags.length < 10) {
    journalDraft.tags.push(raw);
  }
}

function removeDraftTag(tag: string) {
  journalDraft.tags = journalDraft.tags.filter((t) => t !== tag);
}

function addDraftChecklistItem() {
  const text = journalDraft.newCheckItem.trim();
  if (!text) return;
  journalDraft.checklist.push({
    id: `chk-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
    text,
    done: false,
  });
  journalDraft.newCheckItem = "";
}

function removeDraftChecklistItem(id: string) {
  journalDraft.checklist = journalDraft.checklist.filter((item) => item.id !== id);
}

async function handleImagePick(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = "";
  if (!file) return;

  if (journalDraft.media_urls.length >= 9) {
    message.warning("单篇手账最多添加 9 张配图");
    return;
  }

  uploadingImage.value = true;
  try {
    const uploaded = await uploadFile(file, "post_attachment");
    journalDraft.media_urls.push(uploaded.url);
    message.success("配图已添加");
  } catch {
    // Fallback to local object URL in offline preview mode
    const localUrl = URL.createObjectURL(file);
    journalDraft.media_urls.push(localUrl);
    message.info("已添加本地预览图");
  } finally {
    uploadingImage.value = false;
  }
}

async function submitJournal() {
  const trimmedTitle = journalDraft.title.trim();
  const trimmedContent = journalDraft.content.trim();
  if (
    !trimmedContent &&
    !trimmedTitle &&
    !journalDraft.checklist.length &&
    !journalDraft.media_urls.length
  ) {
    message.warning("写点今天的心情或添加一条打卡清单吧");
    return;
  }

  if (journalDraft.newCheckItem.trim()) {
    addDraftChecklistItem();
  }
  if (journalDraft.tagInput.trim()) {
    addTagFromInput();
  }

  // 仅填写了第一行短标题时自动作为正文发布，避免用户误填标题框被拦截。
  const finalTitle = trimmedContent ? trimmedTitle : "";
  const finalContent =
    trimmedContent ||
    trimmedTitle ||
    (journalDraft.checklist.length ? "今日打卡记录" : "分享日常瞬间");

  // 自动提取正文中的 #标签 并合并到标签列表。
  const inlineTags = Array.from(
    finalContent.matchAll(/#([\p{L}\p{N}_-]{1,24})/gu),
    (match) => match[1]!.trim(),
  ).filter(Boolean);
  const mergedTags = Array.from(new Set([...journalDraft.tags, ...inlineTags])).slice(0, 12);

  try {
    await createJournalMutation.mutateAsync({
      entry_date: journalDraft.entry_date || todayDateString(),
      title: finalTitle,
      content: finalContent,
      mood: journalDraft.mood,
      weather: journalDraft.weather,
      location: journalDraft.location.trim(),
      visibility: journalDraft.visibility,
      is_pinned: journalDraft.is_pinned,
      card_theme: journalDraft.card_theme,
      tags: mergedTags,
      media_urls: [...journalDraft.media_urls],
      checklist: [...journalDraft.checklist],
    });
    journalDraft.title = "";
    journalDraft.content = "";
    journalDraft.location = "";
    journalDraft.is_pinned = false;
    journalDraft.media_urls = [];
    journalDraft.checklist = [];
    message.success("手账已保存到你的空间");
    activeTab.value = "journals";
  } catch {
    message.error("保存手账失败，请稍后重试");
  }
}

function selectLedgerCategory(catKey: LedgerCategory) {
  ledgerDraft.category = catKey;
  const meta = getLedgerCategoryMeta(catKey);
  ledgerDraft.kind = meta.defaultKind;
}

async function submitLedgerEntry() {
  const parsedYuan = Number.parseFloat(ledgerDraft.amountYuan);
  if (!Number.isFinite(parsedYuan) || parsedYuan <= 0) {
    message.warning("请输入有效的记账金额");
    return;
  }
  const amountCents = Math.round(parsedYuan * 100);
  const catMeta = getLedgerCategoryMeta(ledgerDraft.category);

  try {
    await createLedgerMutation.mutateAsync({
      entry_date: ledgerDraft.entry_date || todayDateString(),
      kind: ledgerDraft.kind,
      amount_cents: amountCents,
      category: ledgerDraft.category,
      note: ledgerDraft.note.trim() || catMeta.label,
      payment_method: ledgerDraft.payment_method,
    });

    if (ledgerDraft.syncToJournal) {
      await createJournalMutation.mutateAsync({
        entry_date: ledgerDraft.entry_date || todayDateString(),
        title: "",
        content: ledgerDraft.note.trim() || `记一笔${catMeta.label}开销`,
        mood: ledgerDraft.kind === "income" ? "celebrate" : "cozy",
        weather: "sunny",
        location: "",
        visibility: ledgerDraft.journalVisibility,
        is_pinned: false,
        card_theme: "paper",
        tags: ["随手记账", catMeta.label],
        media_urls: [],
        checklist: [],
        ledger_snapshot: {
          single_entry: {
            kind: ledgerDraft.kind,
            category: ledgerDraft.category,
            amount_cents: amountCents,
            note: ledgerDraft.note.trim() || catMeta.label,
          },
        },
      });
    }

    ledgerDraft.amountYuan = "";
    ledgerDraft.note = "";
    message.success(
      ledgerDraft.syncToJournal ? "已记入账本并生成手账卡片" : "已记入私人账本",
    );
  } catch {
    message.error("记账失败，请稍后重试");
  }
}

async function shareMonthlyBillToJournal(
  visibility: JournalVisibility,
  hideExactAmount = false,
) {
  const summary = ledgerSummary.value;
  if (!summary || summary.entry_count === 0) {
    message.warning("本月还没有记账记录，先记一笔吧");
    return;
  }

  try {
    await createJournalMutation.mutateAsync({
      entry_date: todayDateString(),
      title: `${summary.month} 月度生活账单小结`,
      content: hideExactAmount
        ? `整理了 ${summary.month} 的消费结构，共记录 ${summary.entry_count} 笔生活收支，保持有节奏的生活方式。`
        : `${summary.month} 共记录 ${summary.entry_count} 笔收支，把钱花在真正带来快乐和成长的地方。`,
      mood: "focused",
      weather: "sunny",
      location: "月度复盘",
      visibility,
      is_pinned: false,
      card_theme: "sky",
      tags: ["月度账单", "生活复盘"],
      media_urls: [],
      checklist: [],
      ledger_snapshot: {
        month: summary.month,
        total_expense_cents: summary.total_expense_cents,
        total_income_cents: summary.total_income_cents,
        entry_count: summary.entry_count,
        hide_exact_amount: hideExactAmount,
        top_categories: summary.category_breakdown.slice(0, 4).map((c) => ({
          category: c.category,
          ratio_percent: c.ratio_percent,
          amount_cents: c.amount_cents,
        })),
      },
    });
    message.success(
      visibility === "public"
        ? "已生成月度账单手账卡并公开到个人空间"
        : "已生成私密月度账单手账卡",
    );
    activeTab.value = "journals";
  } catch {
    message.error("生成账单手账卡失败");
  }
}

async function saveSpaceSettings(payload: {
  space_title: string;
  space_subtitle: string;
  cover_preset: SpaceCoverPreset;
  monthly_budget_cents: number;
}) {
  try {
    await updateSettingsMutation.mutateAsync(payload);
    settingsOpen.value = false;
    message.success("空间装扮与预算设置已保存");
  } catch {
    message.error("保存失败，请稍后重试");
  }
}

async function handleTogglePin(entry: SpaceJournalItem) {
  try {
    await updateJournalMutation.mutateAsync({
      id: entry.id,
      payload: { is_pinned: !entry.is_pinned },
    });
  } catch {
    message.error("更新置顶状态失败");
  }
}

async function handleToggleVisibility(entry: SpaceJournalItem) {
  const nextVis = entry.visibility === "private" ? "public" : "private";
  try {
    await updateJournalMutation.mutateAsync({
      id: entry.id,
      payload: { visibility: nextVis },
    });
    message.success(nextVis === "public" ? "已设为公开到个人主页" : "已设为仅自己可见");
  } catch {
    message.error("切换可见性失败，请稍后重试");
  }
}

async function handleToggleChecklist(entry: SpaceJournalItem, itemId: string) {
  const nextChecklist = (entry.checklist ?? []).map((item) =>
    item.id === itemId ? { ...item, done: !item.done } : item,
  );
  try {
    await updateJournalMutation.mutateAsync({
      id: entry.id,
      payload: { checklist: nextChecklist },
    });
  } catch {
    message.error("更新打卡状态失败");
  }
}

async function handleRemoveJournal(entry: SpaceJournalItem) {
  if (typeof window !== "undefined" && !window.confirm("确定要删除这篇手账吗？")) {
    return;
  }
  try {
    await deleteJournalMutation.mutateAsync(entry.id);
    message.success("手账已删除");
  } catch {
    message.error("删除手账失败，请稍后重试");
  }
}

async function handleLikeJournal(entry: SpaceJournalItem) {
  try {
    await likeJournalMutation.mutateAsync(entry.id);
  } catch {
    message.error("点赞失败，请稍后重试");
  }
}

async function handleDeleteLedger(item: SpaceLedgerItem) {
  try {
    await deleteLedgerMutation.mutateAsync(item.id);
    message.success("账单记录已删除");
  } catch {
    message.error("删除账单失败，请稍后重试");
  }
}

function scrollToComposer(mode: ComposerMode) {
  composerMode.value = mode;
  composerRef.value?.scrollIntoView({ behavior: "smooth", block: "center" });
}
</script>

<template>
  <div class="space-page">
    <!-- Moments 风格个人空间封面顶栏 -->
    <section
      class="space-hero"
      :class="`space-hero--${activeCoverPreset}`"
      aria-label="个人空间封面"
    >
      <div class="space-hero__pattern" aria-hidden="true"></div>
      <div class="space-hero__inner">
        <div class="space-hero__identity">
          <div class="space-hero__avatar-wrap">
            <UiAvatar
              :name="currentUser?.display_name || currentUser?.username || '手账'"
              :src="resolveApiAssetUrl(currentUser?.avatar_url)"
              size="lg"
            />
            <span class="space-hero__mood-badge" title="今日状态">✨</span>
          </div>
          <div class="space-hero__copy">
            <div class="space-hero__title-row">
              <h1>{{ displaySpaceTitle }}</h1>
              <span class="space-hero__pill">圈子 · 个人空间</span>
            </div>
            <p class="space-hero__subtitle">{{ displaySpaceSubtitle }}</p>
            <div class="space-hero__stats">
              <span><b>{{ recordedDaysCount }}</b> 记录天数</span>
              <span><b>{{ myJournals.length }}</b> 篇手账</span>
              <span><b>{{ publicJournalsCount }}</b> 篇公开日签</span>
              <span v-if="ledgerSummary">
                本月支出 <b>{{ formatCentsToYuan(ledgerSummary.total_expense_cents) }}</b>
              </span>
            </div>
          </div>
        </div>

        <div class="space-hero__actions">
          <button
            type="button"
            class="space-hero__btn space-hero__btn--glass"
            @click="settingsOpen = !settingsOpen"
          >
            🎨 空间装扮 / 预算
          </button>
          <RouterLink
            v-if="currentUser"
            class="space-hero__btn space-hero__btn--glass"
            :to="{ name: 'user-profile', params: { id: currentUser.id } }"
          >
            👤 公开主页视角
          </RouterLink>
          <RouterLink
            v-else
            class="space-hero__btn space-hero__btn--primary"
            :to="{ name: 'auth', query: { redirect: '/space' } }"
          >
            登录同步云端
          </RouterLink>
        </div>
      </div>

      <!-- 空间装扮与月度预算抽屉面板 -->
      <SpaceSettingsDrawer
        v-if="settingsOpen"
        :space-title="settingsDraft.space_title"
        :space-subtitle="settingsDraft.space_subtitle"
        :cover-preset="settingsDraft.cover_preset"
        :monthly-budget-yuan="settingsDraft.monthlyBudgetYuan"
        :saving="updateSettingsMutation.isPending.value"
        @save="saveSpaceSettings"
        @close="settingsOpen = false"
      />
    </section>

    <!-- 登录后本地草稿一键同步提示 -->
    <div
      v-if="isLoggedIn && !localSyncBannerDismissed && pendingLocalSummary.totalCount > 0"
      class="space-sync-banner"
      role="status"
    >
      <span>
        检测到本地保存了
        <template v-if="pendingLocalSummary.journalCount > 0">
          {{ pendingLocalSummary.journalCount }} 篇手账
        </template>
        <template v-if="pendingLocalSummary.journalCount > 0 && pendingLocalSummary.ledgerCount > 0">
          和
        </template>
        <template v-if="pendingLocalSummary.ledgerCount > 0">
          {{ pendingLocalSummary.ledgerCount }} 笔账单
        </template>
        ，是否合并到云端空间？
      </span>
      <div class="space-sync-banner__actions">
        <UiButton
          type="button"
          tone="primary"
          size="sm"
          :loading="syncLocalMutation.isPending.value"
          @click="handleSyncLocalToCloud"
        >
          同步到云端
        </UiButton>
        <UiButton
          type="button"
          tone="ghost"
          size="sm"
          @click="localSyncBannerDismissed = true"
        >
          暂不同步
        </UiButton>
      </div>
    </div>

    <!-- 云端加载失败提示 -->
    <UiCard v-if="isLoggedIn && workspaceQuery.isError.value" class="space-error-banner">
      <span>云端个人空间加载失败，请检查网络或重新登录后再试。</span>
      <UiButton type="button" tone="subtle" size="sm" @click="workspaceQuery.refetch()">
        重新加载
      </UiButton>
    </UiCard>

    <!-- 顶部主视图切换栏（移动端与桌面端自适应） -->
    <nav class="space-nav-bar" aria-label="个人空间模块切换">
      <div class="space-nav-tabs">
        <button
          type="button"
          :class="{ active: activeTab === 'journals' }"
          @click="activeTab = 'journals'"
        >
          <span>📖 我的手账</span>
          <em>{{ myJournals.length }}</em>
        </button>
        <button
          type="button"
          :class="{ active: activeTab === 'ledger' }"
          @click="activeTab = 'ledger'"
        >
          <span>💰 随手记账</span>
          <em>{{ ledgerSummary?.entry_count ?? 0 }}</em>
        </button>
        <button
          type="button"
          :class="{ active: activeTab === 'community' }"
          @click="activeTab = 'community'"
        >
          <span>🌍 圈友手账墙</span>
        </button>
      </div>

      <div class="space-nav-quick">
        <button
          type="button"
          class="space-mobile-cal-toggle"
          @click="mobileCalendarExpanded = !mobileCalendarExpanded"
        >
          🗓️ {{ selectedMonth }} 心情日历
          <span>{{ mobileCalendarExpanded ? "收起" : "展开" }}</span>
        </button>
        <RouterLink class="space-back-forum" :to="{ name: 'forum-home' }">
          🏛️ 公共论坛 →
        </RouterLink>
      </div>
    </nav>

    <!-- 主体三栏布局：左侧圈子/论坛导航 + 中央手账/记账区 + 右侧心情日历 -->
    <div class="space-workspace-grid">
      <aside class="space-left-rail" aria-label="圈子与论坛导航">
        <div class="space-left-rail__panel">
          <div class="space-left-rail__item is-active">
            <span class="rail-item-icon" aria-hidden="true">📖</span>
            <span class="rail-item-copy">
              <strong>私密圈</strong>
              <em>手账 · 记账 · 圈友</em>
            </span>
          </div>

          <RouterLink class="space-left-rail__item is-forum" :to="{ name: 'forum-home' }">
            <span class="rail-item-icon" aria-hidden="true">🏛️</span>
            <span class="rail-item-copy">
              <strong>公共论坛</strong>
              <em>版块讨论 · 精华帖</em>
            </span>
          </RouterLink>

          <nav class="space-left-rail__links" aria-label="社区快捷入口">
            <RouterLink :to="{ name: 'board-directory' }">📂 全部版块</RouterLink>
            <RouterLink :to="{ name: 'user-directory' }">👥 社区成员</RouterLink>
            <RouterLink :to="{ name: 'new-topic' }">✍️ 发布主题</RouterLink>
          </nav>
        </div>
      </aside>

      <main class="space-main-column">
        <!-- Memos + ezBookkeeping 双模极速发布台 -->
        <div ref="composerRef" class="space-composer-anchor" aria-hidden="true"></div>
        <UiCard class="space-composer">
          <div class="space-composer__mode-bar">
            <button
              type="button"
              :class="{ active: composerMode === 'journal' }"
              @click="composerMode = 'journal'"
            >
              ✍️ 写手账 / 碎碎念
            </button>
            <button
              type="button"
              :class="{ active: composerMode === 'ledger' }"
              @click="composerMode = 'ledger'"
            >
              💸 随手记一笔账
            </button>
          </div>

          <!-- 模式 A：写手账 -->
          <div v-if="composerMode === 'journal'" class="space-composer__journal">
            <!-- 心情贴纸横向选择条 -->
            <div class="composer-picker-row">
              <span class="picker-label">今日心情</span>
              <div class="mood-scroll-strip" role="radiogroup" aria-label="选择心情贴纸">
                <button
                  v-for="m in JOURNAL_MOODS"
                  :key="m.key"
                  type="button"
                  class="mood-pill"
                  :class="{ active: journalDraft.mood === m.key }"
                  :style="{ '--mood-color': m.color, '--mood-bg': m.softBg }"
                  @click="journalDraft.mood = m.key"
                >
                  <em>{{ m.emoji }}</em>
                  <span>{{ m.label }}</span>
                </button>
              </div>
            </div>

            <!-- 天气与信纸底纹选择 -->
            <div class="composer-sub-pickers">
              <div class="weather-strip" aria-label="选择天气">
                <button
                  v-for="w in JOURNAL_WEATHERS"
                  :key="w.key"
                  type="button"
                  class="weather-chip"
                  :class="{ active: journalDraft.weather === w.key }"
                  :title="w.label"
                  @click="journalDraft.weather = w.key"
                >
                  {{ w.emoji }} {{ w.label }}
                </button>
              </div>

              <div class="theme-strip" aria-label="选择信纸底纹">
                <button
                  v-for="t in JOURNAL_CARD_THEMES"
                  :key="t.key"
                  type="button"
                  class="theme-dot"
                  :class="{ active: journalDraft.card_theme === t.key }"
                  :style="{ backgroundColor: t.swatch }"
                  :title="`信纸：${t.label}`"
                  @click="journalDraft.card_theme = t.key"
                >
                  <span>{{ t.label }}</span>
                </button>
              </div>
            </div>

            <div class="composer-inputs" :class="`composer-inputs--${journalDraft.card_theme}`">
              <input
                v-model="journalDraft.title"
                type="text"
                class="composer-title-input"
                maxlength="120"
                placeholder="标题（选填，例如：周末通关手记 / 今日小确幸）"
              />
              <textarea
                v-model="journalDraft.content"
                rows="3"
                class="composer-body-input"
                maxlength="4000"
                placeholder="记下此刻的闪念、读到的一句话或日常碎片…"
              ></textarea>

              <!-- 打卡清单编辑区 -->
              <div v-if="journalDraft.checklist.length || journalDraft.showTools" class="composer-checklist-box">
                <div
                  v-for="item in journalDraft.checklist"
                  :key="item.id"
                  class="composer-check-item"
                >
                  <input v-model="item.done" type="checkbox" />
                  <span>{{ item.text }}</span>
                  <button type="button" @click="removeDraftChecklistItem(item.id)">×</button>
                </div>
                <div class="composer-check-add">
                  <input
                    v-model="journalDraft.newCheckItem"
                    type="text"
                    maxlength="120"
                    placeholder="添加一条今日小目标/打卡项，回车添加…"
                    @keydown.enter.prevent="addDraftChecklistItem"
                  />
                  <button type="button" @click="addDraftChecklistItem">+ 添加</button>
                </div>
              </div>

              <!-- 已选配图预览 -->
              <div v-if="journalDraft.media_urls.length" class="composer-media-preview">
                <div
                  v-for="(url, idx) in journalDraft.media_urls"
                  :key="`${url}-${idx}`"
                  class="composer-media-thumb"
                >
                  <img :src="resolveApiAssetUrl(url)" alt="已上传配图" />
                  <button
                    type="button"
                    aria-label="移除配图"
                    @click="journalDraft.media_urls.splice(idx, 1)"
                  >
                    ×
                  </button>
                </div>
              </div>

              <!-- 标签与地点扩展栏 -->
              <div class="composer-tags-bar">
                <span v-for="tag in journalDraft.tags" :key="tag" class="draft-tag">
                  #{{ tag }}
                  <i @click="removeDraftTag(tag)">×</i>
                </span>
                <input
                  v-model="journalDraft.tagInput"
                  type="text"
                  maxlength="24"
                  placeholder="+ 标签 (回车)"
                  @keydown.enter.prevent="addTagFromInput"
                  @blur="addTagFromInput"
                />
                <input
                  v-model="journalDraft.location"
                  type="text"
                  maxlength="40"
                  class="composer-location-input"
                  placeholder="📍 地点/场景（如：书桌前）"
                />
                <input
                  v-model="journalDraft.entry_date"
                  type="date"
                  class="composer-date-input"
                  aria-label="手账日期"
                />
              </div>
            </div>

            <div class="space-composer__footer">
              <div class="composer-tools">
                <input
                  ref="imageInputRef"
                  type="file"
                  accept="image/png,image/jpeg,image/gif,image/webp"
                  class="sr-only-file"
                  @change="handleImagePick"
                />
                <button
                  type="button"
                  class="tool-btn"
                  :disabled="uploadingImage"
                  @click="imageInputRef?.click()"
                >
                  🖼️ {{ uploadingImage ? "上传中…" : "配图" }}
                </button>
                <button
                  type="button"
                  class="tool-btn"
                  :class="{ active: journalDraft.showTools }"
                  @click="journalDraft.showTools = !journalDraft.showTools"
                >
                  ☑️ 打卡清单
                </button>
                <label class="pin-check">
                  <input v-model="journalDraft.is_pinned" type="checkbox" />
                  <span>📌 置顶</span>
                </label>
              </div>

              <div class="composer-submit-group">
                <select
                  v-model="journalDraft.visibility"
                  class="visibility-select"
                  aria-label="手账可见性"
                >
                  <option value="public">🌐 公开到个人空间</option>
                  <option value="private">🔒 仅自己可见</option>
                </select>
                <UiButton
                  type="button"
                  tone="primary"
                  :disabled="createJournalMutation.isPending.value"
                  @click="submitJournal"
                >
                  {{ createJournalMutation.isPending.value ? "保存中…" : "发布手账" }}
                </UiButton>
              </div>
            </div>
          </div>

          <!-- 模式 B：随手记一笔账 -->
          <div v-else class="space-composer__ledger">
            <div class="ledger-top-row">
              <div class="ledger-kind-switch">
                <button
                  type="button"
                  :class="{ active: ledgerDraft.kind === 'expense' }"
                  @click="ledgerDraft.kind = 'expense'"
                >
                  支出
                </button>
                <button
                  type="button"
                  :class="{ active: ledgerDraft.kind === 'income' }"
                  @click="ledgerDraft.kind = 'income'"
                >
                  收入
                </button>
              </div>

              <div class="ledger-amount-box">
                <span class="currency">¥</span>
                <input
                  v-model="ledgerDraft.amountYuan"
                  type="number"
                  step="0.01"
                  min="0.01"
                  inputmode="decimal"
                  placeholder="0.00"
                />
              </div>

              <input
                v-model="ledgerDraft.entry_date"
                type="date"
                class="composer-date-input"
                aria-label="记账日期"
              />
            </div>

            <div class="ledger-category-grid" role="radiogroup" aria-label="收支分类">
              <button
                v-for="cat in LEDGER_CATEGORIES"
                :key="cat.key"
                type="button"
                class="ledger-cat-btn"
                :class="{ active: ledgerDraft.category === cat.key }"
                :style="{ '--cat-color': cat.color, '--cat-bg': cat.softBg }"
                @click="selectLedgerCategory(cat.key)"
              >
                <em>{{ cat.emoji }}</em>
                <span>{{ cat.label }}</span>
              </button>
            </div>

            <div class="ledger-note-row">
              <input
                v-model="ledgerDraft.note"
                type="text"
                maxlength="140"
                placeholder="一句话备注（例如：买独立游戏 / 桂花拿铁 / 稿费入账）"
                @keydown.enter.prevent="submitLedgerEntry"
              />
              <select v-model="ledgerDraft.payment_method" aria-label="支付方式">
                <option v-for="pm in LEDGER_PAYMENT_METHODS" :key="pm.key" :value="pm.key">
                  {{ pm.label }}
                </option>
              </select>
            </div>

            <div class="space-composer__footer">
              <label class="sync-journal-toggle">
                <input v-model="ledgerDraft.syncToJournal" type="checkbox" />
                <span>✨ 同时生成一张带账单胶囊的手账日签</span>
              </label>

              <div class="composer-submit-group">
                <select
                  v-if="ledgerDraft.syncToJournal"
                  v-model="ledgerDraft.journalVisibility"
                  class="visibility-select"
                >
                  <option value="private">🔒 手账仅自己可见</option>
                  <option value="public">🌐 手账公开到空间</option>
                </select>
                <span v-else class="private-hint">🔒 账本明细默认严格仅自己可见</span>
                <UiButton
                  type="button"
                  tone="primary"
                  :disabled="createLedgerMutation.isPending.value"
                  @click="submitLedgerEntry"
                >
                  {{ createLedgerMutation.isPending.value ? "记录中…" : "记入账本" }}
                </UiButton>
              </div>
            </div>
          </div>
        </UiCard>

        <!-- Tab 1: 我的手账时间轴 -->
        <section v-if="activeTab === 'journals'" class="space-feed-section" aria-label="我的手账时间线">
          <!-- 筛选状态条 -->
          <div class="space-filter-bar">
            <div class="space-filter-pills">
              <button
                type="button"
                :class="{ active: filterVisibility === 'all' }"
                @click="filterVisibility = 'all'"
              >
                全部 ({{ myJournals.length }})
              </button>
              <button
                type="button"
                :class="{ active: filterVisibility === 'public' }"
                @click="filterVisibility = 'public'"
              >
                🌐 公开 ({{ publicJournalsCount }})
              </button>
              <button
                type="button"
                :class="{ active: filterVisibility === 'private' }"
                @click="filterVisibility = 'private'"
              >
                🔒 私密 ({{ myJournals.length - publicJournalsCount }})
              </button>
            </div>

            <input
              v-model="filterKeyword"
              type="search"
              class="space-filter-search"
              placeholder="🔍 搜索手账内容、地点或标签…"
              aria-label="搜索我的手账"
            />

            <div v-if="hasActiveJournalFilters" class="space-active-filters">
              <span v-if="filterDate" class="filter-chip">
                📅 {{ filterDate }}
                <i @click="filterDate = ''">×</i>
              </span>
              <span v-if="filterMood" class="filter-chip">
                {{ getMoodMeta(filterMood).emoji }} {{ getMoodMeta(filterMood).label }}
                <i @click="filterMood = ''">×</i>
              </span>
              <span v-if="filterTag" class="filter-chip">
                #{{ filterTag }}
                <i @click="filterTag = ''">×</i>
              </span>
              <button type="button" class="clear-filter-btn" @click="clearJournalFilters">
                重置筛选
              </button>
            </div>
          </div>

          <div v-if="filteredJournals.length" class="space-journal-timeline">
            <SpaceJournalCard
              v-for="item in filteredJournals"
              :key="item.id"
              :entry="item"
              :editable="true"
              @like="handleLikeJournal"
              @toggle-pin="handleTogglePin"
              @toggle-visibility="handleToggleVisibility"
              @toggle-checklist="handleToggleChecklist"
              @remove="handleRemoveJournal"
              @select-tag="(t) => (filterTag = filterTag === t ? '' : t)"
            />
          </div>

          <UiCard v-else class="space-empty-card">
            <span class="empty-emoji">📒</span>
            <strong>没有匹配的手账记录</strong>
            <p>
              {{
                hasActiveJournalFilters
                  ? "尝试清除日期或标签筛选，查看更多历史手账。"
                  : "在上方挑选一个今日心情贴纸，写下第一篇属于你的手账吧！"
              }}
            </p>
            <UiButton
              v-if="hasActiveJournalFilters"
              type="button"
              tone="subtle"
              @click="clearJournalFilters"
            >
              清除筛选条件
            </UiButton>
          </UiCard>
        </section>

        <!-- Tab 2: 随手记账与月度报表 -->
        <SpaceLedgerPanel
          v-else-if="activeTab === 'ledger'"
          :selected-month="selectedMonth"
          :ledger-summary="ledgerSummary"
          :ledgers="myLedgers"
          :budget-usage-percent="budgetUsagePercent"
          :remaining-budget-cents="remainingBudgetCents"
          @share-monthly-bill="shareMonthlyBillToJournal"
          @delete-ledger="handleDeleteLedger"
          @compose-ledger="scrollToComposer('ledger')"
        />

        <!-- Tab 3: 圈友手账墙（公共公开流） -->
        <section v-else class="space-community-section" aria-label="圈友公开手账墙">
          <div class="community-intro-banner">
            <div>
              <strong>🌍 圈友公开手账墙</strong>
              <p>这里汇集了圈友们设为「公开」的日常手账、心情日签与月度小结卡片。点击作者头像或关注按钮，把喜欢的圈友收进自己的关注流。</p>
            </div>
            <div class="space-filter-pills community-scope-pills">
              <button
                type="button"
                :class="{ active: communityScope === 'all' }"
                @click="communityScope = 'all'"
              >
                全部公开
              </button>
              <button
                type="button"
                :class="{ active: communityScope === 'following' }"
                @click="communityScope = 'following'"
              >
                我关注的
              </button>
            </div>
          </div>

          <UiCard v-if="communityFeedQuery.isLoading.value" class="space-empty-card">
            正在加载圈友手账…
          </UiCard>
          <div
            v-else-if="visibleCommunityFeed.length"
            class="space-journal-timeline"
          >
            <SpaceJournalCard
              v-for="item in visibleCommunityFeed"
              :key="item.id"
              :entry="item"
              :show-author="true"
              :editable="Boolean(currentUser && item.user_id === currentUser.id)"
              :show-follow="Boolean(currentUser && item.author && item.user_id !== currentUser.id)"
              :is-following="Boolean(item.author?.username && followingUsernames.has(item.author.username))"
              :follow-busy="Boolean(item.author?.username && followBusyUsername === item.author.username)"
              @like="handleLikeJournal"
              @toggle-pin="handleTogglePin"
              @toggle-visibility="handleToggleVisibility"
              @toggle-checklist="handleToggleChecklist"
              @toggle-follow="handleToggleFollowAuthor"
              @remove="handleRemoveJournal"
              @select-tag="
                (t) => {
                  activeTab = 'journals';
                  filterTag = t;
                }
              "
            />
          </div>
          <UiCard v-else class="space-empty-card">
            <span class="empty-emoji">✨</span>
            <strong>{{ communityScope === 'following' ? '还没有关注圈友的公开手账' : '还没有公开的圈友手账' }}</strong>
            <p>
              {{
                communityScope === 'following'
                  ? '先去「全部公开」里逛逛，关注几位喜欢的圈友吧。'
                  : '发布第一篇设为「公开」的手账日签，点亮圈友手账墙吧！'
              }}
            </p>
          </UiCard>
        </section>
      </main>

      <!-- 右侧贴边栏：心情像素日历 + 账本速览 + 标签云 -->
      <aside
        class="space-sidebar"
        :class="{ 'is-mobile-open': mobileCalendarExpanded }"
        aria-label="心情日历与账本速览"
      >
        <!-- 月度心情与打卡日历 (Daylio / Memos 风格) -->
        <SpaceMoodCalendarCard
          :selected-month="selectedMonth"
          :journals="myJournals"
          :ledgers="myLedgers"
          :filter-date="filterDate"
          :filter-mood="filterMood"
          @shift-month="shiftMonth"
          @select-date="
            (dateStr) => {
              filterDate = filterDate === dateStr ? '' : dateStr;
              activeTab = 'journals';
            }
          "
          @select-mood="
            (moodKey) => {
              filterMood = filterMood === moodKey ? '' : moodKey;
              activeTab = 'journals';
            }
          "
        />

        <!-- 侧栏月度记账速览卡 -->
        <UiCard v-if="ledgerSummary" class="space-side-card space-mini-ledger">
          <header class="side-card-head">
            <strong>💰 本月账本速览</strong>
            <button type="button" class="link-btn" @click="activeTab = 'ledger'">
              详情 →
            </button>
          </header>

          <div class="mini-ledger-numbers">
            <div>
              <span>本月已支出</span>
              <strong>{{ formatCentsToYuan(ledgerSummary.total_expense_cents) }}</strong>
            </div>
            <div>
              <span>预算剩余</span>
              <b :class="{ 'is-over': remainingBudgetCents < 0 }">
                {{ formatCentsToYuan(remainingBudgetCents) }}
              </b>
            </div>
          </div>

          <div class="budget-progress-bar budget-progress-bar--sm">
            <i
              :style="{ width: `${budgetUsagePercent}%` }"
              :class="{ 'is-warn': budgetUsagePercent >= 85 }"
            ></i>
          </div>

          <div v-if="ledgerSummary.category_breakdown.length" class="mini-top-cats">
            <span
              v-for="cat in ledgerSummary.category_breakdown.slice(0, 3)"
              :key="cat.category"
              class="mini-cat-pill"
            >
              {{ getLedgerCategoryMeta(cat.category).emoji }}
              {{ getLedgerCategoryMeta(cat.category).label }}
              <b>{{ cat.ratio_percent }}%</b>
            </span>
          </div>
        </UiCard>

        <!-- 手账标签云 -->
        <UiCard v-if="tagCloud.length" class="space-side-card">
          <header class="side-card-head">
            <strong>🏷️ 我的手账标签</strong>
          </header>
          <div class="side-tag-cloud">
            <button
              v-for="[tag, count] in tagCloud"
              :key="tag"
              type="button"
              :class="{ active: filterTag === tag }"
              @click="
                filterTag = filterTag === tag ? '' : tag;
                activeTab = 'journals';
              "
            >
              #{{ tag }} <em>{{ count }}</em>
            </button>
          </div>
        </UiCard>
      </aside>
    </div>

    <!-- 移动端底部悬浮快记按钮 -->
    <div class="space-mobile-fab-group" aria-label="移动端快捷记录">
      <button
        type="button"
        class="space-mobile-fab space-mobile-fab--primary"
        @click="scrollToComposer('journal')"
      >
        ✍️ 写手账
      </button>
      <button
        type="button"
        class="space-mobile-fab space-mobile-fab--secondary"
        @click="scrollToComposer('ledger')"
      >
        💸 记一笔
      </button>
    </div>
  </div>
</template>

<style scoped lang="scss" src="./SpacePage.scss"></style>
