export type JournalMood =
  | "happy"
  | "focused"
  | "calm"
  | "cozy"
  | "inspired"
  | "tired"
  | "rainy"
  | "celebrate";

export type JournalWeather = "sunny" | "cloudy" | "breezy" | "rainy" | "snowy" | "night";

export type JournalVisibility = "public" | "private";

export type JournalCardTheme = "paper" | "sky" | "mint" | "sunset" | "lavender" | "grid";

export type SpaceCoverPreset = "aurora" | "sunset" | "meadow" | "paper" | "starlight";

export type LedgerKind = "expense" | "income";

export type LedgerCategory =
  | "dining"
  | "coffee"
  | "gaming"
  | "shopping"
  | "transit"
  | "entertainment"
  | "housing"
  | "salary"
  | "other";

export type LedgerPaymentMethod = "wechat" | "alipay" | "card" | "cash";

export interface SpaceChecklistItem {
  id: string;
  text: string;
  done: boolean;
}

export interface SpaceLedgerSnapshot {
  month?: string;
  total_expense_cents?: number;
  total_income_cents?: number;
  entry_count?: number;
  hide_exact_amount?: boolean;
  top_categories?: Array<{
    category: string;
    ratio_percent: number;
    amount_cents?: number;
  }>;
  single_entry?: {
    kind: LedgerKind;
    category: LedgerCategory;
    amount_cents: number;
    note: string;
  };
}

export interface SpaceJournalAuthorBrief {
  id: string;
  username: string;
  display_name?: string | null;
  avatar_url?: string | null;
  level: number;
}

export interface SpaceJournalItem {
  id: string;
  user_id: string;
  entry_date: string;
  title: string;
  content: string;
  mood: JournalMood | string;
  weather: JournalWeather | string;
  location: string;
  visibility: JournalVisibility | string;
  is_pinned: boolean;
  card_theme: JournalCardTheme | string;
  tags: string[];
  media_urls: string[];
  checklist: SpaceChecklistItem[];
  ledger_snapshot?: SpaceLedgerSnapshot | null;
  likes_count: number;
  created_at: string;
  updated_at: string;
  author?: SpaceJournalAuthorBrief | null;
}

export interface SpaceLedgerItem {
  id: string;
  user_id: string;
  entry_date: string;
  kind: LedgerKind | string;
  amount_cents: number;
  category: LedgerCategory | string;
  note: string;
  payment_method: LedgerPaymentMethod | string;
  created_at: string;
  updated_at: string;
}

export interface SpaceLedgerCategoryBreakdown {
  category: string;
  amount_cents: number;
  count: number;
  ratio_percent: number;
}

export interface SpaceLedgerMonthlySummary {
  month: string;
  total_expense_cents: number;
  total_income_cents: number;
  monthly_budget_cents: number;
  entry_count: number;
  category_breakdown: SpaceLedgerCategoryBreakdown[];
}

export interface SpaceSetting {
  user_id: string;
  space_title: string;
  space_subtitle: string;
  cover_preset: SpaceCoverPreset;
  monthly_budget_cents: number;
}

export interface SpaceMyWorkspace {
  settings: SpaceSetting;
  journals: SpaceJournalItem[];
  ledger_entries: SpaceLedgerItem[];
  ledger_summary: SpaceLedgerMonthlySummary;
}

export interface SpacePublicProfile {
  user_id: string;
  username: string;
  display_name?: string | null;
  avatar_url?: string | null;
  bio?: string | null;
  space_title: string;
  space_subtitle: string;
  cover_preset: SpaceCoverPreset | string;
  public_journal_count: number;
  journals: SpaceJournalItem[];
}

export interface SpaceJournalCreatePayload {
  entry_date: string;
  title?: string;
  content: string;
  mood: JournalMood;
  weather: JournalWeather;
  location?: string;
  visibility: JournalVisibility;
  is_pinned?: boolean;
  card_theme: JournalCardTheme;
  tags: string[];
  media_urls: string[];
  checklist: SpaceChecklistItem[];
  ledger_snapshot?: SpaceLedgerSnapshot | null;
}

export interface SpaceJournalUpdatePayload {
  entry_date?: string;
  title?: string;
  content?: string;
  mood?: JournalMood;
  weather?: JournalWeather;
  location?: string;
  visibility?: JournalVisibility;
  is_pinned?: boolean;
  card_theme?: JournalCardTheme;
  tags?: string[];
  media_urls?: string[];
  checklist?: SpaceChecklistItem[];
  ledger_snapshot?: SpaceLedgerSnapshot | null;
}

export interface SpaceLedgerCreatePayload {
  entry_date: string;
  kind: LedgerKind;
  amount_cents: number;
  category: LedgerCategory;
  note: string;
  payment_method: LedgerPaymentMethod;
}

export interface MoodMeta {
  key: JournalMood;
  emoji: string;
  label: string;
  color: string;
  softBg: string;
}

export const JOURNAL_MOODS: MoodMeta[] = [
  { key: "happy", emoji: "😊", label: "开心", color: "#ea580c", softBg: "#fff7ed" },
  { key: "focused", emoji: "🎯", label: "专注", color: "#0284c7", softBg: "#e0f2fe" },
  { key: "calm", emoji: "🍵", label: "平静", color: "#059669", softBg: "#ecfdf5" },
  { key: "cozy", emoji: "☕", label: "惬意", color: "#b45309", softBg: "#fef3c7" },
  { key: "inspired", emoji: "✨", label: "灵感", color: "#7c3aed", softBg: "#f5f3ff" },
  { key: "celebrate", emoji: "🎉", label: "小确幸", color: "#db2777", softBg: "#fdf2f8" },
  { key: "tired", emoji: "🔋", label: "充电中", color: "#64748b", softBg: "#f1f5f9" },
  { key: "rainy", emoji: "🌧️", label: "听雨", color: "#4f46e5", softBg: "#eef2ff" },
];

export const JOURNAL_WEATHERS: Array<{ key: JournalWeather; emoji: string; label: string }> = [
  { key: "sunny", emoji: "☀️", label: "晴朗" },
  { key: "cloudy", emoji: "⛅", label: "多云" },
  { key: "breezy", emoji: "🍃", label: "微风" },
  { key: "rainy", emoji: "🌧️", label: "落雨" },
  { key: "snowy", emoji: "❄️", label: "初雪" },
  { key: "night", emoji: "🌙", label: "星夜" },
];

export const JOURNAL_CARD_THEMES: Array<{
  key: JournalCardTheme;
  label: string;
  swatch: string;
}> = [
  { key: "paper", label: "暖白纸笺", swatch: "#fffdf9" },
  { key: "grid", label: "方格手账", swatch: "#f8fafc" },
  { key: "sky", label: "晴空微蓝", swatch: "#f0f9ff" },
  { key: "mint", label: "薄荷森林", swatch: "#f0fdf4" },
  { key: "sunset", label: "杏仁暖橘", swatch: "#fff7ed" },
  { key: "lavender", label: "星夜紫雾", swatch: "#f5f3ff" },
];

export const SPACE_COVER_PRESETS: Array<{
  key: SpaceCoverPreset;
  label: string;
  desc: string;
}> = [
  { key: "aurora", label: "极光青蓝", desc: "清新通透的平行线经典天空色调" },
  { key: "sunset", label: "暮光暖橘", desc: "傍晚书桌旁的柔和暖阳手账感" },
  { key: "meadow", label: "森系薄荷", desc: "自然呼吸感的森林草木绿意" },
  { key: "paper", label: "奶油纸本", desc: "极简温暖的复古方格手账封面" },
  { key: "starlight", label: "静谧星夜", desc: "适合深夜独处与灵感记录的深邃蓝紫" },
];

export interface LedgerCategoryMeta {
  key: LedgerCategory;
  emoji: string;
  label: string;
  color: string;
  softBg: string;
  defaultKind: LedgerKind;
}

export const LEDGER_CATEGORIES: LedgerCategoryMeta[] = [
  { key: "dining", emoji: "🍜", label: "餐饮美食", color: "#ea580c", softBg: "#fff7ed", defaultKind: "expense" },
  { key: "coffee", emoji: "🧋", label: "咖啡饮品", color: "#b45309", softBg: "#fef3c7", defaultKind: "expense" },
  { key: "gaming", emoji: "🎮", label: "游戏数码", color: "#6366f1", softBg: "#eef2ff", defaultKind: "expense" },
  { key: "shopping", emoji: "🛍️", label: "日用购物", color: "#db2777", softBg: "#fdf2f8", defaultKind: "expense" },
  { key: "transit", emoji: "🚇", label: "出行交通", color: "#0284c7", softBg: "#e0f2fe", defaultKind: "expense" },
  { key: "entertainment", emoji: "🎬", label: "休闲文化", color: "#8b5cf6", softBg: "#f5f3ff", defaultKind: "expense" },
  { key: "housing", emoji: "🏠", label: "居住账单", color: "#0d9488", softBg: "#f0fdfa", defaultKind: "expense" },
  { key: "salary", emoji: "💎", label: "收入进账", color: "#10b981", softBg: "#ecfdf5", defaultKind: "income" },
  { key: "other", emoji: "📦", label: "其他杂项", color: "#64748b", softBg: "#f1f5f9", defaultKind: "expense" },
];

export const LEDGER_PAYMENT_METHODS: Array<{ key: LedgerPaymentMethod; label: string }> = [
  { key: "wechat", label: "微信" },
  { key: "alipay", label: "支付宝" },
  { key: "card", label: "银行卡" },
  { key: "cash", label: "现金/其他" },
];

export function getMoodMeta(mood: string): MoodMeta {
  return JOURNAL_MOODS.find((item) => item.key === mood) ?? JOURNAL_MOODS[0]!;
}

export function getWeatherMeta(weather: string): { key: JournalWeather; emoji: string; label: string } {
  return JOURNAL_WEATHERS.find((item) => item.key === weather) ?? JOURNAL_WEATHERS[0]!;
}

export function getLedgerCategoryMeta(category: string): LedgerCategoryMeta {
  return LEDGER_CATEGORIES.find((item) => item.key === category) ?? LEDGER_CATEGORIES[0]!;
}

export function formatCentsToYuan(cents: number, showPlus = false): string {
  const yuan = (Math.abs(cents) / 100).toFixed(2);
  const prefix = cents < 0 ? "-" : showPlus && cents > 0 ? "+" : "";
  return `${prefix}¥${yuan}`;
}

export function todayDateString(): string {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function currentMonthString(): string {
  return todayDateString().slice(0, 7);
}
