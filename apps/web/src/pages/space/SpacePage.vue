<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import { message } from "ant-design-vue";

import { useCurrentUser } from "@/features/auth/queries";
import SpaceJournalCard from "@/features/space/components/SpaceJournalCard.vue";
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
  SPACE_COVER_PRESETS,
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
  useUpdateSpaceJournal,
  useUpdateSpaceSettings,
} from "@/features/space/queries";
import { uploadFile } from "@/features/uploads/api";
import { hasAccessToken, resolveApiAssetUrl } from "@/shared/api/client";
import UiAvatar from "@/shared/ui/Avatar.vue";
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";

type SpaceMainTab = "journals" | "ledger" | "community";
type ComposerMode = "journal" | "ledger";

const currentUserQuery = useCurrentUser();
const currentUser = computed(() => currentUserQuery.data.value);
const isLoggedIn = computed(() => Boolean(currentUser.value || hasAccessToken()));

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
const filterVisibility = ref<"all" | "public" | "private">("all");

const workspaceQuery = useMySpaceWorkspace(selectedMonth);
const communityFeedQuery = usePublicSpaceFeed(
  30,
  computed(() => activeTab.value === "community"),
);

const createJournalMutation = useCreateSpaceJournal();
const updateJournalMutation = useUpdateSpaceJournal();
const deleteJournalMutation = useDeleteSpaceJournal();
const likeJournalMutation = useLikeSpaceJournal();
const createLedgerMutation = useCreateSpaceLedgerEntry();
const deleteLedgerMutation = useDeleteSpaceLedgerEntry();
const updateSettingsMutation = useUpdateSpaceSettings();

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
const hideExactAmountOnShare = ref(false);

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
  return myJournals.value.filter((item) => {
    if (filterDate.value && item.entry_date !== filterDate.value) return false;
    if (filterMood.value && item.mood !== filterMood.value) return false;
    if (filterTag.value && !item.tags?.includes(filterTag.value)) return false;
    if (filterVisibility.value !== "all" && item.visibility !== filterVisibility.value) {
      return false;
    }
    return true;
  });
});

const hasActiveJournalFilters = computed(() =>
  Boolean(
    filterDate.value ||
      filterMood.value ||
      filterTag.value ||
      filterVisibility.value !== "all",
  ),
);

function clearJournalFilters() {
  filterDate.value = "";
  filterMood.value = "";
  filterTag.value = "";
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

// Calendar Grid Builder for selectedMonth (YYYY-MM)
const calendarCells = computed(() => {
  const [yearStr, monthStr] = selectedMonth.value.split("-");
  const year = Number(yearStr) || new Date().getFullYear();
  const month = Number(monthStr) || new Date().getMonth() + 1;
  const firstDayWeek = new Date(year, month - 1, 1).getDay();
  const daysInMonth = new Date(year, month, 0).getDate();

  const journalByDate = new Map<string, SpaceJournalItem>();
  for (const j of myJournals.value) {
    if (j.entry_date.startsWith(selectedMonth.value) && !journalByDate.has(j.entry_date)) {
      journalByDate.set(j.entry_date, j);
    }
  }

  const ledgerCountByDate = new Map<string, number>();
  for (const l of myLedgers.value) {
    if (l.entry_date.startsWith(selectedMonth.value)) {
      ledgerCountByDate.set(l.entry_date, (ledgerCountByDate.get(l.entry_date) ?? 0) + 1);
    }
  }

  const cells: Array<{
    key: string;
    dayNumber: number | null;
    dateStr: string;
    moodEmoji: string | null;
    moodColor: string | null;
    hasLedger: boolean;
    isToday: boolean;
  }> = [];

  for (let i = 0; i < firstDayWeek; i += 1) {
    cells.push({
      key: `pad-${i}`,
      dayNumber: null,
      dateStr: "",
      moodEmoji: null,
      moodColor: null,
      hasLedger: false,
      isToday: false,
    });
  }

  const today = todayDateString();
  for (let d = 1; d <= daysInMonth; d += 1) {
    const dateStr = `${year}-${String(month).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
    const journal = journalByDate.get(dateStr);
    const moodMeta = journal ? getMoodMeta(journal.mood) : null;
    cells.push({
      key: dateStr,
      dayNumber: d,
      dateStr,
      moodEmoji: moodMeta ? moodMeta.emoji : null,
      moodColor: moodMeta ? moodMeta.softBg : null,
      hasLedger: (ledgerCountByDate.get(dateStr) ?? 0) > 0,
      isToday: dateStr === today,
    });
  }
  return cells;
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

const monthLedgersGrouped = computed(() => {
  const prefix = `${selectedMonth.value}-`;
  const list = myLedgers.value.filter((item) => item.entry_date.startsWith(prefix));
  const groups = new Map<
    string,
    { date: string; items: SpaceLedgerItem[]; dayExpense: number; dayIncome: number }
  >();
  for (const item of list) {
    const group = groups.get(item.entry_date) ?? {
      date: item.entry_date,
      items: [],
      dayExpense: 0,
      dayIncome: 0,
    };
    group.items.push(item);
    if (item.kind === "income") {
      group.dayIncome += item.amount_cents;
    } else {
      group.dayExpense += item.amount_cents;
    }
    groups.set(item.entry_date, group);
  }
  return Array.from(groups.values());
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
  if (!journalDraft.content.trim() && !journalDraft.checklist.length) {
    message.warning("写点今天的心情或添加一条打卡清单吧");
    return;
  }

  if (journalDraft.newCheckItem.trim()) {
    addDraftChecklistItem();
  }
  if (journalDraft.tagInput.trim()) {
    addTagFromInput();
  }

  try {
    await createJournalMutation.mutateAsync({
      entry_date: journalDraft.entry_date || todayDateString(),
      title: journalDraft.title.trim(),
      content: journalDraft.content.trim() || "今日打卡记录",
      mood: journalDraft.mood,
      weather: journalDraft.weather,
      location: journalDraft.location.trim(),
      visibility: journalDraft.visibility,
      is_pinned: journalDraft.is_pinned,
      card_theme: journalDraft.card_theme,
      tags: [...journalDraft.tags],
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

async function shareMonthlyBillToJournal(visibility: JournalVisibility) {
  const summary = ledgerSummary.value;
  if (!summary || summary.entry_count === 0) {
    message.warning("本月还没有记账记录，先记一笔吧");
    return;
  }

  try {
    await createJournalMutation.mutateAsync({
      entry_date: todayDateString(),
      title: `${summary.month} 月度生活账单小结`,
      content: hideExactAmountOnShare.value
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
        hide_exact_amount: hideExactAmountOnShare.value,
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

async function saveSpaceSettings() {
  const budgetYuan = Number.parseFloat(settingsDraft.monthlyBudgetYuan);
  const budgetCents =
    Number.isFinite(budgetYuan) && budgetYuan >= 0 ? Math.round(budgetYuan * 100) : 300000;

  try {
    await updateSettingsMutation.mutateAsync({
      space_title: settingsDraft.space_title.trim(),
      space_subtitle: settingsDraft.space_subtitle.trim(),
      cover_preset: settingsDraft.cover_preset,
      monthly_budget_cents: budgetCents,
    });
    settingsOpen.value = false;
    message.success("空间装扮与预算设置已保存");
  } catch {
    message.error("保存失败，请稍后重试");
  }
}

function handleTogglePin(entry: SpaceJournalItem) {
  updateJournalMutation.mutate({
    id: entry.id,
    payload: { is_pinned: !entry.is_pinned },
  });
}

function handleToggleVisibility(entry: SpaceJournalItem) {
  const nextVis = entry.visibility === "private" ? "public" : "private";
  updateJournalMutation.mutate({
    id: entry.id,
    payload: { visibility: nextVis },
  });
  message.success(nextVis === "public" ? "已设为公开到个人主页" : "已设为仅自己可见");
}

function handleToggleChecklist(entry: SpaceJournalItem, itemId: string) {
  const nextChecklist = (entry.checklist ?? []).map((item) =>
    item.id === itemId ? { ...item, done: !item.done } : item,
  );
  updateJournalMutation.mutate({
    id: entry.id,
    payload: { checklist: nextChecklist },
  });
}

function handleRemoveJournal(entry: SpaceJournalItem) {
  if (typeof window !== "undefined" && !window.confirm("确定要删除这篇手账吗？")) {
    return;
  }
  deleteJournalMutation.mutate(entry.id);
}

function handleLikeJournal(entry: SpaceJournalItem) {
  likeJournalMutation.mutate(entry.id);
}

function handleDeleteLedger(item: SpaceLedgerItem) {
  deleteLedgerMutation.mutate(item.id);
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
      <div v-if="settingsOpen" class="space-settings-drawer">
        <div class="space-settings-drawer__grid">
          <label>
            <span>空间名称</span>
            <input
              v-model="settingsDraft.space_title"
              type="text"
              maxlength="80"
              placeholder="例如：阿星的光年手账本"
            />
          </label>
          <label>
            <span>空间签名 / 寄语</span>
            <input
              v-model="settingsDraft.space_subtitle"
              type="text"
              maxlength="200"
              placeholder="写一句展示在空间顶部的生活寄语…"
            />
          </label>
          <label>
            <span>每月记账预算（元，仅自己可见）</span>
            <input
              v-model="settingsDraft.monthlyBudgetYuan"
              type="number"
              min="0"
              step="100"
              placeholder="3000"
            />
          </label>
        </div>

        <div class="space-settings-drawer__presets">
          <span>封面视觉主题：</span>
          <div class="preset-pills">
            <button
              v-for="preset in SPACE_COVER_PRESETS"
              :key="preset.key"
              type="button"
              :class="{ active: settingsDraft.cover_preset === preset.key }"
              @click="settingsDraft.cover_preset = preset.key"
            >
              {{ preset.label }}
            </button>
          </div>
        </div>

        <div class="space-settings-drawer__footer">
          <UiButton type="button" tone="primary" @click="saveSpaceSettings">
            保存空间设置
          </UiButton>
          <UiButton type="button" tone="ghost" @click="settingsOpen = false">
            收起
          </UiButton>
        </div>
      </div>
    </section>

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
          ← 返回圈子讨论
        </RouterLink>
      </div>
    </nav>

    <!-- 主体双栏布局 -->
    <div class="space-workspace-grid">
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
                placeholder="可选短标题（如：周末通关手记 / 今日小确幸）"
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
        <section v-else-if="activeTab === 'ledger'" class="space-ledger-section" aria-label="私人记账本">
          <UiCard v-if="ledgerSummary" class="ledger-overview-card">
            <div class="ledger-overview-card__head">
              <div>
                <span class="kicker">🔒 私人月度账本（仅自己可见）</span>
                <h2>{{ selectedMonth }} 收支总览</h2>
              </div>
              <div class="ledger-share-box">
                <label class="hide-amount-check">
                  <input v-model="hideExactAmountOnShare" type="checkbox" />
                  <span>仅晒比例（隐藏金额）</span>
                </label>
                <UiButton
                  type="button"
                  tone="subtle"
                  @click="shareMonthlyBillToJournal('public')"
                >
                  📊 生成月度小结手账卡
                </UiButton>
              </div>
            </div>

            <div class="ledger-metrics-grid">
              <div class="metric-item">
                <span>本月支出</span>
                <strong class="is-expense">
                  {{ formatCentsToYuan(ledgerSummary.total_expense_cents) }}
                </strong>
              </div>
              <div class="metric-item">
                <span>本月收入</span>
                <strong class="is-income">
                  {{ formatCentsToYuan(ledgerSummary.total_income_cents, true) }}
                </strong>
              </div>
              <div class="metric-item">
                <span>预算剩余</span>
                <strong :class="{ 'is-over': remainingBudgetCents < 0 }">
                  {{ formatCentsToYuan(remainingBudgetCents) }}
                </strong>
              </div>
            </div>

            <div class="budget-progress-wrap">
              <div class="budget-progress-labels">
                <span>
                  月度预算进度（预算 {{ formatCentsToYuan(ledgerSummary.monthly_budget_cents) }}）
                </span>
                <b>已用 {{ budgetUsagePercent }}%</b>
              </div>
              <div class="budget-progress-bar">
                <i
                  :style="{ width: `${budgetUsagePercent}%` }"
                  :class="{ 'is-warn': budgetUsagePercent >= 85 }"
                ></i>
              </div>
            </div>

            <div v-if="ledgerSummary.category_breakdown.length" class="ledger-breakdown-list">
              <h3>支出分类占比</h3>
              <div
                v-for="cat in ledgerSummary.category_breakdown"
                :key="cat.category"
                class="breakdown-row"
              >
                <span class="cat-badge">
                  <em>{{ getLedgerCategoryMeta(cat.category).emoji }}</em>
                  <b>{{ getLedgerCategoryMeta(cat.category).label }}</b>
                  <small>{{ cat.count }} 笔</small>
                </span>
                <div class="cat-track">
                  <i
                    :style="{
                      width: `${Math.max(5, cat.ratio_percent)}%`,
                      backgroundColor: getLedgerCategoryMeta(cat.category).color,
                    }"
                  ></i>
                </div>
                <span class="cat-amount">
                  {{ formatCentsToYuan(cat.amount_cents) }} ({{ cat.ratio_percent }}%)
                </span>
              </div>
            </div>
          </UiCard>

          <!-- 按日分组账单流水 -->
          <div v-if="monthLedgersGrouped.length" class="ledger-day-groups">
            <UiCard v-for="group in monthLedgersGrouped" :key="group.date" class="ledger-day-card">
              <header class="ledger-day-card__head">
                <strong>📅 {{ group.date }}</strong>
                <div class="day-sums">
                  <span v-if="group.dayExpense">支 {{ formatCentsToYuan(group.dayExpense) }}</span>
                  <span v-if="group.dayIncome" class="is-income">
                    收 {{ formatCentsToYuan(group.dayIncome, true) }}
                  </span>
                </div>
              </header>

              <ul class="ledger-entry-list">
                <li v-for="item in group.items" :key="item.id" class="ledger-entry-row">
                  <span
                    class="entry-cat-icon"
                    :style="{
                      backgroundColor: getLedgerCategoryMeta(item.category).softBg,
                      color: getLedgerCategoryMeta(item.category).color,
                    }"
                  >
                    {{ getLedgerCategoryMeta(item.category).emoji }}
                  </span>
                  <div class="entry-info">
                    <strong>{{ getLedgerCategoryMeta(item.category).label }}</strong>
                    <p>{{ item.note || "无备注" }}</p>
                  </div>
                  <div class="entry-right">
                    <b :class="item.kind === 'income' ? 'is-income' : 'is-expense'">
                      {{
                        formatCentsToYuan(
                          item.kind === "income" ? item.amount_cents : -item.amount_cents,
                          true,
                        )
                      }}
                    </b>
                    <button
                      type="button"
                      class="entry-del-btn"
                      title="删除此笔记录"
                      @click="handleDeleteLedger(item)"
                    >
                      删除
                    </button>
                  </div>
                </li>
              </ul>
            </UiCard>
          </div>

          <UiCard v-else class="space-empty-card">
            <span class="empty-emoji">🪙</span>
            <strong>{{ selectedMonth }} 还没有记账流水</strong>
            <p>使用上方「随手记一笔账」记录日常咖啡、餐饮或游戏开销，月底可一键生成漂亮的手账小结卡。</p>
            <UiButton type="button" tone="primary" @click="scrollToComposer('ledger')">
              记第一笔账
            </UiButton>
          </UiCard>
        </section>

        <!-- Tab 3: 圈友手账墙（公共公开流） -->
        <section v-else class="space-community-section" aria-label="圈友公开手账墙">
          <div class="community-intro-banner">
            <div>
              <strong>🌍 圈友公开手账墙</strong>
              <p>这里汇集了圈友们设为「公开」的日常手账、心情日签与月度小结卡片。点击作者头像还能逛逛 TA 的个人主页。</p>
            </div>
          </div>

          <UiCard v-if="communityFeedQuery.isLoading.value" class="space-empty-card">
            正在加载圈友手账…
          </UiCard>
          <div
            v-else-if="communityFeedQuery.data.value && communityFeedQuery.data.value.length"
            class="space-journal-timeline"
          >
            <SpaceJournalCard
              v-for="item in communityFeedQuery.data.value"
              :key="item.id"
              :entry="item"
              :show-author="true"
              :editable="Boolean(currentUser && item.user_id === currentUser.id)"
              @like="handleLikeJournal"
              @toggle-pin="handleTogglePin"
              @toggle-visibility="handleToggleVisibility"
              @toggle-checklist="handleToggleChecklist"
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
            <strong>还没有公开的圈友手账</strong>
            <p>发布第一篇设为「公开」的手账日签，点亮圈友手账墙吧！</p>
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
        <UiCard class="space-side-card space-calendar-card">
          <header class="calendar-header">
            <button type="button" aria-label="上个月" @click="shiftMonth(-1)">‹</button>
            <strong>🗓️ {{ selectedMonth }} 心情日历</strong>
            <button type="button" aria-label="下个月" @click="shiftMonth(1)">›</button>
          </header>

          <div class="calendar-weekdays" aria-hidden="true">
            <span>日</span><span>一</span><span>二</span><span>三</span><span>四</span><span>五</span><span>六</span>
          </div>

          <div class="calendar-grid">
            <button
              v-for="cell in calendarCells"
              :key="cell.key"
              type="button"
              class="calendar-cell"
              :disabled="!cell.dayNumber"
              :class="{
                'is-empty': !cell.dayNumber,
                'is-today': cell.isToday,
                'is-selected': cell.dateStr && filterDate === cell.dateStr,
                'has-mood': Boolean(cell.moodEmoji),
              }"
              :style="cell.moodColor ? { '--cell-bg': cell.moodColor } : undefined"
              @click="
                cell.dateStr &&
                (filterDate = filterDate === cell.dateStr ? '' : cell.dateStr,
                (activeTab = 'journals'))
              "
            >
              <template v-if="cell.dayNumber">
                <em v-if="cell.moodEmoji" class="cell-mood">{{ cell.moodEmoji }}</em>
                <span class="cell-num">{{ cell.dayNumber }}</span>
                <i v-if="cell.hasLedger" class="cell-ledger-dot" title="当日有记账"></i>
              </template>
            </button>
          </div>

          <div class="calendar-mood-filter">
            <span>按心情筛选：</span>
            <div class="mood-mini-list">
              <button
                v-for="m in JOURNAL_MOODS"
                :key="m.key"
                type="button"
                :class="{ active: filterMood === m.key }"
                :title="m.label"
                @click="
                  filterMood = filterMood === m.key ? '' : m.key;
                  activeTab = 'journals';
                "
              >
                {{ m.emoji }}
              </button>
            </div>
          </div>
        </UiCard>

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
