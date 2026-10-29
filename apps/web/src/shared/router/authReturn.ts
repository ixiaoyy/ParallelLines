/** Canonical same-origin paths only; kept equivalent to the local OP safe-return core. */
export function safeReturn(value: unknown, origin: string, fallback = "/chat/"): string {
  if (typeof value !== "string" || value.length > 2048 || !value.startsWith("/")) return fallback;
  let decoded = value;
  for (let index = 0; index < 4; index++) {
    if (decoded.startsWith("//") || /[\\\u0000-\u0020\u007f]/.test(decoded)) return fallback;
    const pathname = decoded.split(/[?#]/)[0];
    if (pathname.split("/").some(part => part === "." || part === "..")
      || /%2f|%5c/i.test(pathname)) return fallback;
    let next: string;
    try { next = decodeURIComponent(decoded); } catch { return fallback; }
    if (next === decoded) break;
    decoded = next;
    if (index === 3) return fallback;
  }
  try {
    const url = new URL(value, origin);
    if (url.origin !== origin || url.username || url.password) return fallback;
    return url.pathname + url.search + url.hash;
  } catch { return fallback; }
}

function decodedPath(value: string, origin: string): string {
  let pathname = new URL(value, origin).pathname;
  for (let index = 0; index < 4; index++) {
    const next = decodeURIComponent(pathname);
    if (next === pathname) break;
    pathname = next;
  }
  return pathname;
}

/** Main auth must not return to an auth loop or directly to protocol/API callbacks. */
export function resolveAuthReturn(value: unknown, origin: string, fallback = "/forum"): string {
  const target = safeReturn(value, origin, fallback);
  try {
    const pathname = decodedPath(target, origin);
    if (pathname === "/auth" || (pathname.startsWith("/auth/") && pathname !== "/auth/chat")
      || pathname === "/api" || pathname.startsWith("/api/")) return fallback;
    return target;
  } catch { return fallback; }
}

/** Chat is an independent application; the connect route also needs a fresh page lifecycle. */
export function needsFullAuthNavigation(value: string, origin: string): boolean {
  const pathname = decodedPath(value, origin);
  return pathname === "/chat" || pathname.startsWith("/chat/") || pathname === "/auth/chat";
}

/** A validated OP interaction is the only login continuation that hides the forum shell. */
export function isChatSsoContinuation(value: unknown, origin: string): boolean {
  const target = resolveAuthReturn(value, origin, "/forum");
  const url = new URL(target, origin);
  const interactions = url.searchParams.getAll("interaction_id");
  return url.pathname === "/auth/chat" && interactions.length === 1
    && /^[A-Za-z0-9_-]{8,128}$/.test(interactions[0]);
}

/** Only the fixed same-origin OP finish path may receive an approval via POST. */
export function trustedChatFinish(value: unknown, origin: string): string | null {
  if (typeof value !== "string" || /[\\\u0000-\u0020\u007f]/.test(value)) return null;
  try {
    const url = new URL(value, origin);
    if (url.origin !== origin || url.username || url.password || url.search || url.hash
      || url.pathname !== "/auth/oidc/interaction/finish") return null;
    return url.href;
  } catch { return null; }
}
