const HEX_COLOR_PATTERN = /^#[0-9a-fA-F]{6}$/;

export type PublicSettingMap = Record<string, unknown>;

export function applySiteBranding(settings: PublicSettingMap | undefined, preview?: PublicSettingMap): void {
  if (typeof document === "undefined") {
    return;
  }

  const merged = { ...(settings ?? {}), ...(preview ?? {}) };
  const root = document.documentElement;
  const primary = normalizeLegacyPrimaryColor(settingString(merged, "brand_primary_color", "#409eff"));
  const accent = settingString(merged, "brand_accent_color", "#10b981");

  applyColor(root, "--primary", "--primary-rgb", primary);
  applyColor(root, "--accent-geek", "--accent-geek-rgb", accent);
  if (HEX_COLOR_PATTERN.test(primary)) {
    root.style.setProperty("--brand-blue", primary);
  }

  /* 链接/点缀悬停与主按钮体系对齐（不随品牌色变深） */
  root.style.setProperty("--primary-hover", "#66b1ff");
  root.style.setProperty("--primary-active", "#3a8ee6");

  /* 主题色固定 #409EFF（实心按钮 + --theme-soft-* 透底悬停） */
  const theme = {
    "--theme-primary": "#409eff",
    "--theme-primary-hover": "#66b1ff",
    "--theme-primary-active": "#3a8ee6",
    "--theme-primary-rgb": "64, 158, 255",
    "--btn-primary-bg": "#409eff",
    "--btn-primary-bg-hover": "#66b1ff",
    "--btn-primary-border": "#409eff",
    "--btn-primary-border-hover": "#66b1ff",
    "--btn-primary-active": "#3a8ee6",
    "--theme-soft-fg": "#409eff",
    "--theme-soft-fg-hover": "#66b1ff",
    "--theme-soft-bg": "color-mix(in srgb, #409eff 12%, transparent)",
    "--theme-soft-bg-hover": "color-mix(in srgb, #409eff 18%, transparent)",
    "--theme-soft-border": "color-mix(in srgb, #409eff 22%, #e2e8f0)",
    "--theme-soft-border-hover": "color-mix(in srgb, #409eff 38%, #e2e8f0)",
    "--theme-focus-ring": "#a3d3ff",
  } as const;
  for (const [key, value] of Object.entries(theme)) {
    root.style.setProperty(key, value);
  }

  const faviconUrl = settingString(merged, "brand_favicon_url", "/favicon.svg");
  updateFavicon(faviconUrl);

  const siteTitle = settingString(merged, "site_title", "平行线");
  document.title = siteTitle;
}

function applyColor(root: HTMLElement, colorVar: string, rgbVar: string, color: string): void {
  if (!HEX_COLOR_PATTERN.test(color)) {
    return;
  }

  root.style.setProperty(colorVar, color);
  root.style.setProperty(rgbVar, hexToRgb(color));
}

function updateFavicon(url: string): void {
  const safeUrl = safeAssetUrl(url) ? url : "/favicon.svg";
  let link = document.querySelector<HTMLLinkElement>('link[rel="icon"]');
  if (!link) {
    link = document.createElement("link");
    link.rel = "icon";
    document.head.append(link);
  }
  link.href = safeUrl;
}

function settingString(settings: PublicSettingMap, key: string, fallback: string): string {
  const value = settings[key];
  return typeof value === "string" && value.trim() ? value.trim() : fallback;
}

function normalizeLegacyPrimaryColor(color: string): string {
  return parseHexColor(color) === 23208 ? "#409eff" : color;
}

function safeAssetUrl(url: string): boolean {
  if (Array.from(url).some((char) => /\s/.test(char))) {
    return false;
  }
  return url.startsWith("/") || url.startsWith("https://") || url.startsWith("http://");
}

function hexToRgb(hex: string): string {
  const value = hex.replace("#", "");
  const red = Number.parseInt(value.slice(0, 2), 16);
  const green = Number.parseInt(value.slice(2, 4), 16);
  const blue = Number.parseInt(value.slice(4, 6), 16);
  return `${red}, ${green}, ${blue}`;
}

function parseHexColor(hex: string): number | null {
  const value = hex.trim().replace("#", "");
  return /^[0-9a-fA-F]{6}$/.test(value) ? Number.parseInt(value, 16) : null;
}
