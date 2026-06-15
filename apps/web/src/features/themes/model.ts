export interface ThemePackage {
  id: string;
  name: string;
  description: string;
  settings: Record<string, string>;
  assets?: string[];
  scripts?: string[];
}

export const THEME_PACKAGES: ThemePackage[] = [
  {
    id: "parallel-calm",
    name: "Parallel Calm",
    description: "默认蓝青色调，适合技术社区长期阅读。",
    settings: { brand_primary_color: "#409EFF", brand_accent_color: "#08C7D8" },
    assets: ["/logo-lines-mark.png"],
  },
  {
    id: "forest-focus",
    name: "Forest Focus",
    description: "绿色强调色，适合知识库和问答型社区。",
    settings: { brand_primary_color: "#047857", brand_accent_color: "#10B981" },
    assets: ["/logo-lines-mark.png"],
  },
  {
    id: "ember-support",
    name: "Ember Support",
    description: "暖色高对比，用于客服和运营场景。",
    settings: { brand_primary_color: "#B45309", brand_accent_color: "#F97316" },
    assets: ["/logo-lines-mark.png"],
  },
];

const HEX_COLOR_PATTERN = /^#[0-9a-fA-F]{6}$/;

export function validateThemePackage(theme: ThemePackage): string[] {
  const issues: string[] = [];
  if (theme.scripts?.length) {
    issues.push("theme_scripts_forbidden");
  }
  for (const [key, value] of Object.entries(theme.settings)) {
    if (key.endsWith("_color") && !HEX_COLOR_PATTERN.test(value)) {
      issues.push(`invalid_color:${key}`);
    }
  }
  for (const asset of theme.assets ?? []) {
    if (!asset.startsWith("/") || asset.includes("..") || /\s/.test(asset)) {
      issues.push("unsafe_asset_url");
    }
  }
  return issues;
}
