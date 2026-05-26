const HEX_COLOR_PATTERN = /^#[0-9a-fA-F]{6}$/;

export type PublicSettingMap = Record<string, unknown>;

export function applySiteBranding(settings: PublicSettingMap | undefined, preview?: PublicSettingMap): void {
  if (typeof document === "undefined") {
    return;
  }

  const merged = { ...(settings ?? {}), ...(preview ?? {}) };
  const root = document.documentElement;
  const primary = settingString(merged, "brand_primary_color", "#409eff");
  const accent = settingString(merged, "brand_accent_color", "#10b981");

  applyColor(root, "--primary", "--primary-rgb", primary);
  applyColor(root, "--accent-geek", "--accent-geek-rgb", accent);
  if (HEX_COLOR_PATTERN.test(primary)) {
    root.style.setProperty("--brand-blue", primary);
    /* 悬停略亮，勿与 #0f172a 混色（会把按钮压成深蓝） */
    root.style.setProperty("--primary-hover", `color-mix(in srgb, ${primary} 88%, #ffffff)`);
    root.style.setProperty("--primary-active", `color-mix(in srgb, ${primary} 86%, #1e293b)`);
  }

  /* 主按钮色固定 #409EFF，与 AGENTS.md 一致，不随 brand_primary_color 漂移 */
  root.style.setProperty("--btn-primary-bg", "#409eff");
  root.style.setProperty("--btn-primary-bg-hover", "#66b1ff");
  root.style.setProperty("--btn-primary-border", "#409eff");
  root.style.setProperty("--btn-primary-border-hover", "#66b1ff");
  root.style.setProperty("--btn-primary-active", "#3a8ee6");

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
