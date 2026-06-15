/**
 * 版块 / 标签 色彩唯一配置源
 * --------------------------------
 * 修改 BOARD_PALETTE 中任意色值，刷新页面即可全局生效。
 * 通过 injectBoardPalette() 注入 .board-tone-N 的 CSS 变量。
 */

export type BoardToneDefinition = {
  tone: number;
  /** 固定 slug 映射（优先级最高） */
  slugs: string[];
  accent: string;
  accentRgb: string;
  tintBg: string;
  markBg: string;
  markFg: string;
  markBorder: string;
};

/** ★ 全局色板：改这里即可 */
export const BOARD_PALETTE: BoardToneDefinition[] = [
  {
    tone: 1,
    slugs: ["resources", "benefits", "deals", "experience", "engineering", "dev"],
    accent: "#ea580c",
    accentRgb: "234, 88, 12",
    tintBg: "color-mix(in srgb, #fff7ed 82%, #ffffff)",
    markBg: "color-mix(in srgb, #fb923c 22%, #ffffff)",
    markFg: "#c2410c",
    markBorder: "rgba(234, 88, 12, 0.28)",
  },
  {
    tone: 2,
    slugs: ["health", "qna", "questions", "support"],
    accent: "#65a30d",
    accentRgb: "132, 204, 22",
    tintBg: "color-mix(in srgb, #f7fee7 82%, #ffffff)",
    markBg: "color-mix(in srgb, #84cc16 20%, #ffffff)",
    markFg: "#4d7c0f",
    markBorder: "rgba(132, 204, 22, 0.26)",
  },
  {
    tone: 3,
    slugs: ["news", "frontier", "frontend"],
    accent: "#6366f1",
    accentRgb: "99, 102, 241",
    tintBg: "color-mix(in srgb, #f5f3ff 82%, #ffffff)",
    markBg: "color-mix(in srgb, #818cf8 20%, #ffffff)",
    markFg: "#5b21b6",
    markBorder: "rgba(99, 102, 241, 0.24)",
  },
  {
    tone: 4,
    slugs: ["announcements", "official", "memory-notes"],
    accent: "#ca8a04",
    accentRgb: "234, 179, 8",
    tintBg: "color-mix(in srgb, #fefce8 84%, #ffffff)",
    markBg: "color-mix(in srgb, #facc15 24%, #ffffff)",
    markFg: "#a16207",
    markBorder: "rgba(234, 179, 8, 0.28)",
  },
  {
    tone: 5,
    slugs: ["reading", "comics", "manga", "plugins"],
    accent: "#db2777",
    accentRgb: "219, 39, 119",
    tintBg: "color-mix(in srgb, #fdf2f8 82%, #ffffff)",
    markBg: "color-mix(in srgb, #f472b6 18%, #ffffff)",
    markFg: "#be185d",
    markBorder: "rgba(219, 39, 119, 0.22)",
  },
  {
    tone: 6,
    slugs: ["feedback", "lounge", "chat", "community"],
    accent: "#475569",
    accentRgb: "148, 163, 184",
    tintBg: "color-mix(in srgb, #f1f5f9 88%, #ffffff)",
    markBg: "color-mix(in srgb, #94a3b8 16%, #ffffff)",
    markFg: "#475569",
    markBorder: "rgba(148, 163, 184, 0.22)",
  },
];

export const BOARD_TONE_COUNT = BOARD_PALETTE.length;

const SLUG_TONE = BOARD_PALETTE.reduce<Record<string, number>>((map, entry) => {
  for (const slug of entry.slugs) {
    map[slug] = entry.tone;
  }
  return map;
}, {});

const PALETTE_STYLE_ID = "board-palette-vars";

function hashKey(value: string): number {
  const normalized = value.trim().toLowerCase();
  let hash = 0;
  for (let i = 0; i < normalized.length; i += 1) {
    hash = (hash + normalized.charCodeAt(i) * (i + 1)) % BOARD_TONE_COUNT;
  }
  return hash + 1;
}

export function getBoardToneIndex(slug: string): number {
  return SLUG_TONE[slug] ?? hashKey(slug);
}

export function getTagToneIndex(tag: string): number {
  return hashKey(tag);
}

export function boardToneClass(slug: string): string {
  return `board-tone-${getBoardToneIndex(slug)}`;
}

export function tagToneClass(tag: string): string {
  return `board-tone-${getTagToneIndex(tag)}`;
}

function buildToneCss(entry: BoardToneDefinition): string {
  const gradient = `linear-gradient(168deg,color-mix(in srgb,${entry.accent} 28%,#ffffff) 0%,${entry.accent} 55%,color-mix(in srgb,${entry.accent} 68%,#1e293b) 100%)`;
  return `.board-tone-${entry.tone}{--board-accent:${entry.accent};--board-accent-rgb:${entry.accentRgb};--board-tint-bg:${entry.tintBg};--board-mark-bg:${entry.markBg};--board-mark-fg:${entry.markFg};--board-mark-border:${entry.markBorder};--gradient-board-mark:${gradient};}`;
}

/** 将色板注入页面（仅执行一次） */
export function injectBoardPalette(): void {
  if (typeof document === "undefined" || document.getElementById(PALETTE_STYLE_ID)) {
    return;
  }

  const style = document.createElement("style");
  style.id = PALETTE_STYLE_ID;
  style.textContent = BOARD_PALETTE.map(buildToneCss).join("");
  document.head.append(style);
}
