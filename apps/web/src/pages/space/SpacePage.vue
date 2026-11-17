<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import { message, Modal as AModal } from "ant-design-vue";

import { useCurrentUser } from "@/features/auth/queries";
import { setUserRelationship } from "@/features/social/api";
import { useUserRelationshipUsers } from "@/features/social/queries";
import SpaceDaySliceModal from "@/features/space/components/SpaceDaySliceModal.vue";
import SpaceJournalCard from "@/features/space/components/SpaceJournalCard.vue";
import SpaceLedgerPanel from "@/features/space/components/SpaceLedgerPanel.vue";
import SpaceMoodCalendarCard from "@/features/space/components/SpaceMoodCalendarCard.vue";
import SpaceSettingsDrawer from "@/features/space/components/SpaceSettingsDrawer.vue";
import { getPendingLocalSpaceSummary, SpaceLocalSyncError, type LocalSpacePendingSummary } from "@/features/space/api";
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
  SPACE_STATUS_PRESETS,
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
  type SpaceJournalCreatePayload,
  type SpaceJournalUpdatePayload,
  type SpaceLedgerMonthlySummary,
  type SpaceLedgerItem,
  type SpaceReactionKind,
} from "@/features/space/model";
import {
  useCreateSpaceJournal,
  useCreateSpaceLedgerEntry,
  useDeleteSpaceJournal,
  useDeleteSpaceLedgerEntry,
  useLikeSpaceJournal,
  useMySpaceWorkspace,
  usePublicSpaceFeed,
  useReactSpaceJournal,
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
const statusPickerOpen = ref(false);
const daySliceDate = ref<string | null>(null);
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
const reactJournalMutation = useReactSpaceJournal();
const createLedgerMutation = useCreateSpaceLedgerEntry();
const deleteLedgerMutation = useDeleteSpaceLedgerEntry();
const updateSettingsMutation = useUpdateSpaceSettings();
const syncLocalMutation = useSyncLocalSpaceToCloud();

const pendingLocalSummary = ref<LocalSpacePendingSummary>({ journalCount: 0, ledgerCount: 0, totalCount: 0 });
const localSyncBannerDismissed = ref(false);
const localDataError = ref("");
const localSyncError = ref("");
const syncNeedsReview = ref(false);

/** 读取待同步计数；存储不可用时保留错误，不让页面初始化失败或伪装空数据。 */
function refreshPendingLocalSummary() {
  try {
    pendingLocalSummary.value = getPendingLocalSpaceSummary();
    localDataError.value = "";
  } catch (error) {
    localDataError.value = error instanceof Error ? error.message : "无法读取本机记录，请勿清空浏览器数据";
  }
}
refreshPendingLocalSummary();

watch(isLoggedIn, (loggedIn) => {
  if (loggedIn) {
    refreshPendingLocalSummary();
  }
});

async function handleSyncLocalToCloud() {
  if (syncNeedsReview.value || syncLocalMutation.isPending.value) return;
  localSyncError.value = "";
  try {
    const result = await syncLocalMutation.mutateAsync();
    refreshPendingLocalSummary();
    message.success(
      `已同步 ${result.journalsSynced} 篇手账和 ${result.ledgersSynced} 笔账单到云端`,
    );
  } catch (error) {
    refreshPendingLocalSummary();
    void queryClient.invalidateQueries({ queryKey: queryKeys.spaceRoot });
    localSyncError.value = error instanceof Error ? error.message : "同步未完成，请先核对云端记录";
    syncNeedsReview.value = error instanceof SpaceLocalSyncError && error.needsCloudReview;
  }
}

// Journal Composer State
/** 新建手账只带技术默认值，不预填用户心情、天气、标签或公开范围。 */
function buildJournalDraft() { return {
  entry_date: todayDateString(),
  title: "",
  content: "",
  mood: "" as JournalMood,
  weather: "" as JournalWeather,
  location: "",
  visibility: "private" as JournalVisibility,
  is_pinned: false,
  card_theme: "paper" as JournalCardTheme,
  tagInput: "",
  tags: [] as string[],
  media_urls: [] as string[],
  checklist: [] as SpaceChecklistItem[],
  newCheckItem: "",
  unlock_at: "",
  showTools: false,
}; }
const journalDraft = reactive(buildJournalDraft());
const journalSaving = ref(false);
const journalError = ref("");
const editingEntry = ref<SpaceJournalItem | null>(null);
let savedNewDraft: ReturnType<typeof buildJournalDraft> | null = null;
let editingInitialDraft: ReturnType<typeof buildJournalDraft> | null = null;

/** 拷贝编辑表单的数组，取消编辑时恢复此前尚未发布的新手账。 */
function copyJournalDraft() {
  return { ...journalDraft, tags: [...journalDraft.tags], media_urls: [...journalDraft.media_urls],
    checklist: journalDraft.checklist.map((item) => ({ ...item })) };
}

/** 将已拆封记录载入同一编辑器；账单快照不进入表单，也不会随正文编辑被覆盖。 */
function editJournal(entry: SpaceJournalItem) {
  if (journalSaving.value || entry.is_locked) return;
  if (editingEntry.value && !window.confirm("切换记录会放弃当前编辑，确定继续吗？")) return;
  if (!editingEntry.value) savedNewDraft = copyJournalDraft();
  Object.assign(journalDraft, {
    ...buildJournalDraft(), entry_date: entry.entry_date, title: entry.title, content: entry.content,
    mood: JOURNAL_MOODS.find((m) => m.key === entry.mood)?.key ?? "",
    weather: JOURNAL_WEATHERS.find((w) => w.key === entry.weather)?.key ?? "",
    location: entry.location, visibility: entry.visibility === "public" ? "public" : entry.visibility === "friends" ? "friends" : "private",
    is_pinned: entry.is_pinned, card_theme: JOURNAL_CARD_THEMES.find((t) => t.key === entry.card_theme)?.key ?? "paper",
    tags: [...entry.tags], media_urls: [...entry.media_urls], checklist: entry.checklist.map((item) => ({ ...item })),
    unlock_at: entry.unlock_at ?? "",
  });
  editingEntry.value = entry;
  editingInitialDraft = copyJournalDraft();
  journalError.value = "";
  scrollToComposer("journal");
}

/** 退出编辑只恢复新建草稿，不写入或删除任何记录。 */
function cancelJournalEdit() {
  Object.assign(journalDraft, savedNewDraft ?? buildJournalDraft());
  editingEntry.value = null; editingInitialDraft = null; savedNewDraft = null;
  journalError.value = "";
}

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
const ledgerSaving = ref(false);
const pendingLedgerJournal = ref<SpaceJournalCreatePayload | null>(null);
const ledgerCardError = ref("");
const monthlyPreview = ref<SpaceLedgerMonthlySummary | null>(null);
const monthlyVisibility = ref<JournalVisibility>("private");
const monthlyHideAmount = ref(true);
const monthlySaving = ref(false);
const monthlyError = ref("");

// Space Settings Modal State
const settingsDraft = reactive({
  space_title: "",
  space_subtitle: "",
  cover_preset: "aurora" as SpaceCoverPreset,
  monthlyBudgetYuan: "",
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
    // 0 沿用未设置预算的语义；真实预算保留到分，避免保存装扮时改变金额。
    settingsDraft.monthlyBudgetYuan = next.monthly_budget_cents > 0
      ? String(next.monthly_budget_cents / 100)
      : "";
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
    // 上传失败不添加刷新后会失效的 blob 地址，也不伪装为已保存的配图。
    message.error("配图上传失败，未添加图片；文字草稿已保留");
  } finally {
    uploadingImage.value = false;
  }
}

async function submitJournal() {
  if (journalSaving.value || uploadingImage.value) return;
  if (journalDraft.newCheckItem.trim()) addDraftChecklistItem();
  if (journalDraft.tagInput.trim()) addTagFromInput();
  const title = journalDraft.title.trim();
  const content = journalDraft.content.trim();
  if (!content && !title && !journalDraft.checklist.length && !journalDraft.media_urls.length) {
    journalError.value = "写点内容、添加图片或清单后再保存";
    return;
  }
  if (journalDraft.visibility === "public" && !window.confirm("这篇手账将公开给所有访客，确定保存并公开吗？")) return;
  // 新建沿用仅标题可作正文的入口；编辑保持标题和正文的独立含义。
  const finalTitle = editingEntry.value ? title : content ? title : "";
  const finalContent = content || (!editingEntry.value ? title : "") || (journalDraft.checklist.length ? "打卡清单" : "图片记录");
  const inlineTags = Array.from(finalContent.matchAll(/#([\p{L}\p{N}_-]{1,24})/gu), (match) => match[1]!).filter(Boolean);
  const tags = editingEntry.value ? [...journalDraft.tags] : Array.from(new Set([...journalDraft.tags, ...inlineTags])).slice(0, 12);
  const payload: SpaceJournalCreatePayload = {
    entry_date: journalDraft.entry_date || todayDateString(), title: finalTitle, content: finalContent,
    mood: journalDraft.mood, weather: journalDraft.weather, location: journalDraft.location.trim(),
    visibility: journalDraft.visibility, is_pinned: journalDraft.is_pinned, card_theme: journalDraft.card_theme,
    tags, media_urls: [...journalDraft.media_urls], checklist: journalDraft.checklist.map((item) => ({ ...item })),
    unlock_at: journalDraft.unlock_at || null,
  };
  journalSaving.value = true;
  journalError.value = "";
  const saveToCloud = hasAccessToken();
  try {
    if (editingEntry.value && editingInitialDraft) {
      // 只提交实际改过的字段；不重写账单快照、历史未知枚举或未修改的个人资料。
      const base = editingInitialDraft;
      const patch: SpaceJournalUpdatePayload = {};
      if (finalTitle !== base.title) patch.title = finalTitle;
      if (finalContent !== base.content) patch.content = finalContent;
      if (journalDraft.entry_date !== base.entry_date) patch.entry_date = payload.entry_date;
      if (journalDraft.mood !== base.mood) patch.mood = payload.mood;
      if (journalDraft.weather !== base.weather) patch.weather = payload.weather;
      if (journalDraft.location !== base.location) patch.location = payload.location;
      if (journalDraft.visibility !== base.visibility) patch.visibility = payload.visibility;
      if (journalDraft.is_pinned !== base.is_pinned) patch.is_pinned = payload.is_pinned;
      if (journalDraft.card_theme !== base.card_theme) patch.card_theme = payload.card_theme;
      if (JSON.stringify(tags) !== JSON.stringify(base.tags)) patch.tags = tags;
      if (JSON.stringify(payload.media_urls) !== JSON.stringify(base.media_urls)) patch.media_urls = payload.media_urls;
      if (JSON.stringify(payload.checklist) !== JSON.stringify(base.checklist)) patch.checklist = payload.checklist;
      if (journalDraft.unlock_at !== base.unlock_at) patch.unlock_at = payload.unlock_at;
      await updateJournalMutation.mutateAsync({ id: editingEntry.value.id, payload: patch });
      cancelJournalEdit();
    } else {
      await createJournalMutation.mutateAsync(payload);
      Object.assign(journalDraft, buildJournalDraft());
    }
    message.success(saveToCloud ? "已保存到云端" : "已保存到本机浏览器，尚未同步云端");
    activeTab.value = "journals";
  } catch (error) {
    journalError.value = error instanceof Error ? error.message : "保存失败，草稿已保留，请重试";
  } finally {
    journalSaving.value = false;
  }
}

function selectLedgerCategory(catKey: LedgerCategory) {
  ledgerDraft.category = catKey;
  const meta = getLedgerCategoryMeta(catKey);
  ledgerDraft.kind = meta.defaultKind;
}

async function submitLedgerEntry() {
  if (ledgerSaving.value || pendingLedgerJournal.value) return;
  const parsedYuan = Number.parseFloat(ledgerDraft.amountYuan);
  if (!Number.isFinite(parsedYuan) || parsedYuan <= 0) {
    message.warning("请输入有效的记账金额"); return;
  }
  if (ledgerDraft.syncToJournal && ledgerDraft.journalVisibility === "public" && !window.confirm("同时生成的手账将公开，包含本笔金额和备注，确定继续吗？")) return;
  const amountCents = Math.round(parsedYuan * 100);
  const catMeta = getLedgerCategoryMeta(ledgerDraft.category);
  const ledgerPayload = {
    entry_date: ledgerDraft.entry_date || todayDateString(), kind: ledgerDraft.kind, amount_cents: amountCents,
    category: ledgerDraft.category, note: ledgerDraft.note.trim() || catMeta.label, payment_method: ledgerDraft.payment_method,
  };
  const card: SpaceJournalCreatePayload | null = ledgerDraft.syncToJournal ? {
    entry_date: ledgerPayload.entry_date, title: "",
    content: ledgerDraft.note.trim() || `记录一笔${catMeta.label}${ledgerDraft.kind === "income" ? "收入" : "支出"}`,
    mood: "", weather: "", location: "", visibility: ledgerDraft.journalVisibility,
    is_pinned: false, card_theme: "paper", tags: ["随手记账", catMeta.label], media_urls: [], checklist: [],
    ledger_snapshot: { single_entry: { kind: ledgerDraft.kind, category: ledgerDraft.category, amount_cents: amountCents, note: ledgerPayload.note } },
  } : null;
  ledgerSaving.value = true;
  ledgerCardError.value = "";
  // 账目和卡片有各自的提交结果，卡片失败时绝不重新创建账目。
  try {
    await createLedgerMutation.mutateAsync(ledgerPayload);
  } catch (error) {
    message.error(error instanceof Error ? error.message : "记账失败，输入已保留");
    ledgerSaving.value = false; return;
  }
  ledgerDraft.amountYuan = ""; ledgerDraft.note = "";
  pendingLedgerJournal.value = card;
  ledgerSaving.value = false;
  if (card) await retryLedgerJournal();
  else message.success(hasAccessToken() ? "已记入云端私人账本" : "已记入本机私人账本");
}

/** 仅重试已保存账目对应的手账卡片，不再次写入账本。 */
async function retryLedgerJournal() {
  if (!pendingLedgerJournal.value || ledgerSaving.value) return;
  ledgerSaving.value = true;
  try {
    await createJournalMutation.mutateAsync(pendingLedgerJournal.value);
    pendingLedgerJournal.value = null; ledgerCardError.value = "";
    message.success(hasAccessToken() ? "账目和手账卡片已保存到云端" : "账目和手账卡片已保存到本机");
  } catch (error) {
    ledgerCardError.value = `账目已保存，手账卡片尚未确认保存。${error instanceof Error ? error.message : "请先核对手账列表，再决定是否重试卡片"}`;
  } finally {
    ledgerSaving.value = false;
  }
}

/** 预览冻结当前月真实统计；打开预览不创建记录，默认仅自己可见。 */
function shareMonthlyBillToJournal(_visibility: JournalVisibility, hideExactAmount = true) {
  const summary = ledgerSummary.value;
  if (!summary || summary.entry_count === 0) return;
  monthlyPreview.value = { ...summary, category_breakdown: summary.category_breakdown.map((item) => ({ ...item })) };
  monthlyVisibility.value = "private"; monthlyHideAmount.value = hideExactAmount; monthlyError.value = "";
}

/** 确认后才创建月度卡；隐藏金额时请求本身就不携带结构化精确金额。 */
async function saveMonthlyBill() {
  const summary = monthlyPreview.value;
  if (!summary || monthlySaving.value) return;
  monthlySaving.value = true;
  try {
    await createJournalMutation.mutateAsync({
      entry_date: todayDateString(), title: `${summary.month} 月度生活账单小结`,
      content: `${summary.month} 共记录 ${summary.entry_count} 笔收支。`,
      mood: "", weather: "", location: "", visibility: monthlyVisibility.value,
      is_pinned: false, card_theme: "sky", tags: ["月度账单", "生活复盘"], media_urls: [], checklist: [],
      ledger_snapshot: {
        month: summary.month, entry_count: summary.entry_count, hide_exact_amount: monthlyHideAmount.value,
        ...(monthlyHideAmount.value ? {} : { total_expense_cents: summary.total_expense_cents, total_income_cents: summary.total_income_cents }),
        top_categories: summary.category_breakdown.slice(0, 4).map((c) => ({ category: c.category, ratio_percent: c.ratio_percent,
          ...(monthlyHideAmount.value ? {} : { amount_cents: c.amount_cents }) })),
      },
    });
    monthlyPreview.value = null; activeTab.value = "journals";
    message.success(hasAccessToken() ? "月度小结已按所选范围保存到云端" : "月度小结已保存到本机，尚未同步云端");
  } catch (error) {
    monthlyError.value = error instanceof Error ? error.message : "保存失败，预览已保留，请重试";
  } finally { monthlySaving.value = false; }
}

async function saveSpaceSettings(payload: {
  space_title: string;
  space_subtitle: string;
  cover_preset: SpaceCoverPreset;
  monthly_budget_cents: number;
  current_status: string;
}) {
  try {
    await updateSettingsMutation.mutateAsync(payload);
    settingsOpen.value = false;
    message.success("空间装扮与预算设置已保存");
  } catch {
    message.error("保存失败，请稍后重试");
  }
}

async function selectQuickStatus(statusText: string) {
  statusPickerOpen.value = false;
  const current = spaceSettings.value;
  try {
    await updateSettingsMutation.mutateAsync({
      space_title: current?.space_title ?? settingsDraft.space_title.trim(),
      space_subtitle: current?.space_subtitle ?? settingsDraft.space_subtitle.trim(),
      cover_preset: current?.cover_preset ?? settingsDraft.cover_preset,
      monthly_budget_cents: current?.monthly_budget_cents ?? 0,
      current_status: statusText,
    });
    message.success(statusText ? `当前状态已设为 ${statusText}` : "已清除当前状态");
  } catch {
    message.error("状态更新失败，请稍后重试");
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
  if (nextVis === "public" && !window.confirm("这篇手账将公开给所有访客，包含其中的正文和账单信息，确定公开吗？")) return;
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

async function handleReactJournal(entry: SpaceJournalItem, kind: SpaceReactionKind) {
  try {
    await reactJournalMutation.mutateAsync({ entryId: entry.id, kind });
  } catch {
    message.error("回应失败，请稍后重试");
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
            <button
              type="button"
              class="space-hero__mood-badge"
              :title="spaceSettings?.current_status ? `此刻：${spaceSettings.current_status}（点击切换）` : '设置此刻状态'"
              @click="statusPickerOpen = !statusPickerOpen"
            >
              {{ spaceSettings?.current_status ? spaceSettings.current_status.split(" ")[0] : "✨" }}
            </button>
            <div v-if="statusPickerOpen" class="space-status-popover" role="menu">
              <button
                v-for="preset in SPACE_STATUS_PRESETS"
                :key="preset"
                type="button"
                :class="{ active: spaceSettings?.current_status === preset }"
                @click="selectQuickStatus(preset)"
              >
                {{ preset }}
              </button>
              <button
                v-if="spaceSettings?.current_status"
                type="button"
                class="is-clear"
                @click="selectQuickStatus('')"
              >
                清除状态
              </button>
            </div>
          </div>
          <div class="space-hero__copy">
            <div class="space-hero__title-row">
              <h1>{{ displaySpaceTitle }}</h1>
              <span class="space-hero__pill">圈子 · 私密圈</span>
              <button
                v-if="spaceSettings?.current_status"
                type="button"
                class="space-hero__live-status"
                @click="statusPickerOpen = !statusPickerOpen"
              >
                {{ spaceSettings.current_status }}
              </button>
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
        :current-status="spaceSettings?.current_status"
        :saving="updateSettingsMutation.isPending.value"
        @save="saveSpaceSettings"
        @close="settingsOpen = false"
      />
    </section>

    <div v-if="workspaceQuery.isError.value || localDataError" class="space-data-error" role="alert">
      <strong>记录暂时无法读取</strong>
      <p>{{ localDataError || (workspaceQuery.error.value instanceof Error ? workspaceQuery.error.value.message : '请重试，不要清空浏览器数据') }}</p>
      <UiButton tone="subtle" @click="refreshPendingLocalSummary(); workspaceQuery.refetch()">重新读取</UiButton>
    </div>

    <div v-if="localSyncError" class="space-data-error" role="alert">
      <p>{{ localSyncError }}</p>
      <UiButton tone="subtle" @click="activeTab = 'journals'; workspaceQuery.refetch()">查看云端记录</UiButton>
    </div>
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
          :disabled="syncNeedsReview"
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

          <!-- 常用记录只展示正文、图片、范围与保存，其他能力按需展开。 -->
          <fieldset v-if="composerMode === 'journal'" class="space-composer__journal composer-fieldset" :disabled="journalSaving">
            <div v-if="editingEntry" class="composer-edit-notice" role="status">
              <strong>正在编辑 {{ editingEntry.entry_date }} 的手账</strong>
              <button type="button" class="link-btn" @click="cancelJournalEdit">取消编辑</button>
            </div>
            <div class="composer-inputs" :class="`composer-inputs--${journalDraft.card_theme}`">
              <textarea v-model="journalDraft.content" rows="3" class="composer-body-input" maxlength="4000"
                aria-label="手账正文" placeholder="写下想记录的事…"></textarea>
              <div v-if="journalDraft.media_urls.length" class="composer-media-preview">
                <div v-for="(url, idx) in journalDraft.media_urls" :key="`${url}-${idx}`" class="composer-media-thumb">
                  <img :src="resolveApiAssetUrl(url)" alt="手账配图" />
                  <button type="button" aria-label="移除配图" @click="journalDraft.media_urls.splice(idx, 1)">×</button>
                </div>
              </div>
            </div>
            <div v-show="journalDraft.showTools" id="journal-more-options" class="composer-more-options">
              <label>标题（选填）<input v-model="journalDraft.title" type="text" class="composer-title-input" maxlength="120" /></label>
              <div class="composer-picker-row">
                <span class="picker-label">心情（选填）</span>
                <div class="mood-scroll-strip" aria-label="选择心情贴纸">
                  <button type="button" class="tool-btn" :aria-pressed="journalDraft.mood === ''" @click="journalDraft.mood = ''">不记录</button>
                  <button v-for="m in JOURNAL_MOODS" :key="m.key" type="button" class="mood-pill"
                    :class="{ active: journalDraft.mood === m.key }" :aria-pressed="journalDraft.mood === m.key"
                    :style="{ '--mood-color': m.color, '--mood-bg': m.softBg }" @click="journalDraft.mood = m.key">
                    <em>{{ m.emoji }}</em><span>{{ m.label }}</span>
                  </button>
                </div>
              </div>
              <div class="weather-strip" aria-label="选择天气">
                <button type="button" class="weather-chip" :aria-pressed="journalDraft.weather === ''" @click="journalDraft.weather = ''">不记录天气</button>
                <button v-for="w in JOURNAL_WEATHERS" :key="w.key" type="button" class="weather-chip"
                  :class="{ active: journalDraft.weather === w.key }" :aria-pressed="journalDraft.weather === w.key" @click="journalDraft.weather = w.key">{{ w.emoji }} {{ w.label }}</button>
              </div>
              <div class="theme-strip" aria-label="选择信纸底纹">
                <button v-for="t in JOURNAL_CARD_THEMES" :key="t.key" type="button" class="theme-dot"
                  :class="{ active: journalDraft.card_theme === t.key }" :aria-pressed="journalDraft.card_theme === t.key"
                  :style="{ backgroundColor: t.swatch }" :title="`信纸：${t.label}`" @click="journalDraft.card_theme = t.key"><span>{{ t.label }}</span></button>
              </div>
              <div class="composer-tags-bar">
                <span v-for="tag in journalDraft.tags" :key="tag" class="draft-tag">#{{ tag }}
                  <button type="button" :aria-label="`移除标签 ${tag}`" @click="removeDraftTag(tag)">×</button>
                </span>
                <input v-model="journalDraft.tagInput" type="text" aria-label="添加标签" maxlength="24" placeholder="标签，回车添加" @keydown.enter.prevent="addTagFromInput" @blur="addTagFromInput" />
                <input v-model="journalDraft.location" type="text" aria-label="地点或场景" maxlength="40" class="composer-location-input" placeholder="地点或场景（选填）" />
                <input v-model="journalDraft.entry_date" type="date" class="composer-date-input" aria-label="手账日期" />
              </div>
              <div class="composer-checklist-box">
                <strong class="picker-label">打卡清单</strong>
                <div v-for="item in journalDraft.checklist" :key="item.id" class="composer-check-item">
                  <input v-model="item.done" type="checkbox" :aria-label="item.text" /><span>{{ item.text }}</span>
                  <button type="button" :aria-label="`移除清单 ${item.text}`" @click="removeDraftChecklistItem(item.id)">×</button>
                </div>
                <div class="composer-check-add">
                  <input v-model="journalDraft.newCheckItem" type="text" maxlength="120" placeholder="添加打卡事项，回车添加" @keydown.enter.prevent="addDraftChecklistItem" />
                  <button type="button" @click="addDraftChecklistItem">添加</button>
                </div>
              </div>
              <div class="composer-tools">
                <label class="pin-check"><input v-model="journalDraft.is_pinned" type="checkbox" /><span>置顶手账</span></label>
                <label class="capsule-date-picker"><span>拆封日（选填）</span><input v-model="journalDraft.unlock_at" type="date" :min="todayDateString()" aria-label="时间胶囊拆封日期" /></label>
              </div>
            </div>
            <p v-if="journalError" class="space-form-error" role="alert">{{ journalError }}；当前草稿未清空。</p>
            <div class="space-composer__footer">
              <div class="composer-tools">
                <input ref="imageInputRef" type="file" accept="image/png,image/jpeg,image/gif,image/webp" class="sr-only-file" @change="handleImagePick" />
                <button type="button" class="tool-btn" :disabled="uploadingImage" @click="imageInputRef?.click()">{{ uploadingImage ? '上传中…' : '添加图片' }}</button>
                <button type="button" class="tool-btn" :aria-expanded="journalDraft.showTools" aria-controls="journal-more-options" @click="journalDraft.showTools = !journalDraft.showTools">{{ journalDraft.showTools ? '收起选项' : '更多选项' }}</button>
              </div>
              <div class="composer-submit-group">
                <select v-model="journalDraft.visibility" class="visibility-select" aria-label="手账可见性">
                  <option value="private">仅自己可见</option><option value="friends">仅互关好友可见</option><option value="public">公开到圈友墙</option>
                </select>
                <UiButton type="button" tone="primary" :disabled="journalSaving || uploadingImage" @click="submitJournal">{{ journalSaving ? '保存中…' : editingEntry ? '保存修改' : journalDraft.visibility === 'public' ? '保存并公开' : '保存手账' }}</UiButton>
              </div>
            </div>
            <span class="private-hint">{{ isLoggedIn ? '保存到当前账号的云端空间' : '保存到本机浏览器；登录后可选择同步云端' }}</span>
          </fieldset>

          <!-- 模式 B：随手记一笔账 -->
          <fieldset v-else class="space-composer__ledger composer-fieldset" :disabled="ledgerSaving">
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
                  :disabled="ledgerSaving || Boolean(pendingLedgerJournal)"
                  @click="submitLedgerEntry"
                >
                  {{ ledgerSaving ? "保存中…" : "记入账本" }}
                </UiButton>
              </div>
            </div>
          </fieldset>
          <div v-if="ledgerCardError" class="space-form-error" role="alert">
            <p>{{ ledgerCardError }}</p>
            <UiButton tone="subtle" :disabled="ledgerSaving" @click="retryLedgerJournal">只重试手账卡片</UiButton>
            <UiButton tone="ghost" :disabled="ledgerSaving" @click="pendingLedgerJournal = null; ledgerCardError = ''">仅保留账目</UiButton>
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
              @react="handleReactJournal"
              @toggle-pin="handleTogglePin"
              @toggle-visibility="handleToggleVisibility"
              @toggle-checklist="handleToggleChecklist"
              @remove="handleRemoveJournal"
              @edit="editJournal"
              @select-tag="(t) => (filterTag = filterTag === t ? '' : t)"
            />
          </div>

          <UiCard v-else class="space-empty-card">
            <span class="empty-emoji">📒</span>
            <strong>{{ hasActiveJournalFilters ? '没有匹配的手账记录' : '还没有手账记录' }}</strong>
            <p>
              {{
                hasActiveJournalFilters
                  ? "尝试清除日期或标签筛选，查看更多历史手账。"
                  : "直接写下第一条记录，默认仅自己可见。"
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
              @react="handleReactJournal"
              @toggle-pin="handleTogglePin"
              @toggle-visibility="handleToggleVisibility"
              @toggle-checklist="handleToggleChecklist"
              @toggle-follow="handleToggleFollowAuthor"
              @remove="handleRemoveJournal"
              @edit="editJournal"
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
              daySliceDate = dateStr;
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
              <b :class="{ 'is-over': ledgerSummary.monthly_budget_cents > 0 && remainingBudgetCents < 0 }">
                {{ ledgerSummary.monthly_budget_cents > 0 ? formatCentsToYuan(remainingBudgetCents) : "未设置" }}
              </b>
            </div>
          </div>

          <!-- 未设置预算时不展示剩余额度或使用进度。 -->
          <div v-if="ledgerSummary.monthly_budget_cents > 0" class="budget-progress-bar budget-progress-bar--sm">
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
    <AModal :open="Boolean(monthlyPreview)" title="预览月度小结" :footer="null" :mask-closable="!monthlySaving" :closable="!monthlySaving" @cancel="!monthlySaving && (monthlyPreview = null)">
      <div v-if="monthlyPreview" class="monthly-preview">
        <h3>{{ monthlyPreview.month }} 月度生活账单小结</h3>
        <p>共记录 {{ monthlyPreview.entry_count }} 笔收支。</p>
        <div v-if="!monthlyHideAmount" class="monthly-preview__amounts">
          <span>支出 {{ formatCentsToYuan(monthlyPreview.total_expense_cents) }}</span>
          <span>收入 {{ formatCentsToYuan(monthlyPreview.total_income_cents) }}</span>
        </div>
        <p v-for="cat in monthlyPreview.category_breakdown.slice(0, 4)" :key="cat.category">{{ getLedgerCategoryMeta(cat.category).label }} {{ cat.ratio_percent }}%</p>
        <label><input v-model="monthlyHideAmount" type="checkbox" :disabled="monthlySaving" /> 仅晒比例（隐藏金额）</label>
        <label>可见范围<select v-model="monthlyVisibility" aria-label="月度小结可见范围" :disabled="monthlySaving"><option value="private">仅自己可见</option><option value="friends">仅互关好友可见</option><option value="public">公开到圈友墙</option></select></label>
        <p class="monthly-preview__notice">{{ monthlyVisibility === 'public' ? monthlyHideAmount ? '确认后将公开笔数和分类比例，不包含精确金额。' : '确认后将公开精确收支金额，请确认愿意分享。' : '保存为私人记录，不会发布到公开圈友墙。' }}</p>
        <p v-if="monthlyError" class="space-form-error" role="alert">{{ monthlyError }}</p>
        <div class="monthly-preview__actions"><UiButton tone="ghost" :disabled="monthlySaving" @click="monthlyPreview = null">取消</UiButton><UiButton :disabled="monthlySaving" @click="saveMonthlyBill">{{ monthlySaving ? '保存中…' : monthlyVisibility === 'public' ? '确认公开发布' : monthlyVisibility === 'friends' ? '确认分享给互关好友' : '保存为私密手账' }}</UiButton></div>
      </div>
    </AModal>
    <!-- 一日生活切片弹窗 -->
    <SpaceDaySliceModal
      v-if="daySliceDate"
      :date="daySliceDate"
      :journals="myJournals"
      :ledgers="myLedgers"
      @close="daySliceDate = null"
      @filter-by-date="
        (d) => {
          filterDate = d;
          activeTab = 'journals';
          daySliceDate = null;
        }
      "
      @write-for-date="
        (d) => {
          journalDraft.entry_date = d;
          daySliceDate = null;
          scrollToComposer('journal');
        }
      "
    />
  </div>
</template>

<style scoped lang="scss" src="./SpacePage.scss"></style>
