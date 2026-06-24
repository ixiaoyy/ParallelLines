const DEFAULT_STATIC_ASSET_BASE_URL = "https://img.pingxingxian.space/static/web";
const configuredStaticAssetBaseUrl = (import.meta.env.VITE_STATIC_ASSET_BASE_URL as string | undefined)?.trim();
const staticAssetBaseUrl = (configuredStaticAssetBaseUrl || DEFAULT_STATIC_ASSET_BASE_URL).replace(/\/+$/, "");

// Resolves a built-in frontend asset against the dedicated static CDN prefix.
// Key parameter `path` is a site-root path such as `/auth-visual/bg.png`; the return value is a URL string.
export function staticAssetUrl(path: string): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return staticAssetBaseUrl ? `${staticAssetBaseUrl}${normalizedPath}` : normalizedPath;
}

// Wraps one URL for safe use inside CSS custom properties that expect a `url(...)` token.
// Key parameter `url` is already resolved; the return value can be assigned to a CSS variable.
export function cssUrl(url: string): string {
  const escapedUrl = url.replace(/["\\\n\r\f]/g, (char) => `\\${char}`);
  return `url("${escapedUrl}")`;
}