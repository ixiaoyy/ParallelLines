interface PersistentCacheEntry<T> {
  value: T;
  updatedAt: number;
}

export function readPersistentCache<T>(
  key: string,
  isValue: (value: unknown) => value is T,
  maxAgeMs: number,
): T | null {
  if (typeof window === "undefined") {
    return null;
  }

  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) {
      return null;
    }

    const parsed = JSON.parse(raw) as Partial<PersistentCacheEntry<unknown>>;
    if (typeof parsed.updatedAt !== "number" || Date.now() - parsed.updatedAt > maxAgeMs) {
      window.localStorage.removeItem(key);
      return null;
    }

    return isValue(parsed.value) ? parsed.value : null;
  } catch {
    return null;
  }
}

export function writePersistentCache<T>(key: string, value: T): void {
  if (typeof window === "undefined") {
    return;
  }

  try {
    const entry: PersistentCacheEntry<T> = {
      value,
      updatedAt: Date.now(),
    };
    window.localStorage.setItem(key, JSON.stringify(entry));
  } catch {
    // Cache is an optimization only; unavailable storage must not block rendering.
  }
}
