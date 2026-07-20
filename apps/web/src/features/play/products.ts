const DEFAULT_MATCH3_URL = "https://webmatch3.pingxingxian.space";

export const match3BaseUrl =
  (import.meta.env.VITE_MATCH3_URL as string | undefined)?.trim() || DEFAULT_MATCH3_URL;

// Adds attribution without exposing identity or session data to the public game.
// `entry` identifies the forum surface that initiated the visit; the return value is a safe absolute URL.
export function match3LaunchUrl(entry: "play-hub"): string {
  try {
    const url = new URL(match3BaseUrl);
    url.searchParams.set("utm_source", "parallellines");
    url.searchParams.set("utm_medium", "product_hub");
    url.searchParams.set("utm_campaign", "playground");
    url.searchParams.set("utm_content", entry);
    return url.toString();
  } catch {
    return DEFAULT_MATCH3_URL;
  }
}
