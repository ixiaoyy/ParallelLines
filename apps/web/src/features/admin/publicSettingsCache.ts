import type { PublicSiteSettingsResponse } from "@/features/admin/model";
import { readPersistentCache, writePersistentCache } from "@/shared/lib/persistentCache";

const PUBLIC_SITE_SETTINGS_CACHE_KEY = "parallellines.siteSettings.public.v1";
const PUBLIC_SITE_SETTINGS_CACHE_TTL_MS = 10 * 60 * 1000;

// Reads the last valid public site settings snapshot for first-paint rendering.
// Return value is a validated settings envelope or null; side effects are limited to expired-cache cleanup.
export function readCachedPublicSiteSettings(): PublicSiteSettingsResponse | null {
  return readPersistentCache(
    PUBLIC_SITE_SETTINGS_CACHE_KEY,
    isPublicSiteSettingsResponse,
    PUBLIC_SITE_SETTINGS_CACHE_TTL_MS,
  );
}

// Persists the latest public site settings after a successful API response.
// `settings` is the API envelope; return value is none. Side effect: writes localStorage when available.
export function cachePublicSiteSettings(settings: PublicSiteSettingsResponse): void {
  writePersistentCache(PUBLIC_SITE_SETTINGS_CACHE_KEY, settings);
}

// Validates the public settings cache envelope before it is used as UI data.
// `value` is unknown localStorage data; return value narrows it to PublicSiteSettingsResponse.
function isPublicSiteSettingsResponse(value: unknown): value is PublicSiteSettingsResponse {
  if (!isRecord(value) || !isRecord(value.settings)) {
    return false;
  }

  return value.updated_at === null || typeof value.updated_at === "string";
}

// Checks whether an unknown value is a non-null object.
// Return value is a type guard only; side effect: none.
function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
