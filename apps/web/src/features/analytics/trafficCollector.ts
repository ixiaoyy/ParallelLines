import { IS_FORUM_SITE } from "@/shared/site/links";

/** 显式开启后，仅在首屏加载和浏览器空闲后安装采集器；不等待网络、不读取身份凭据。 */
export function installTrafficCollector(): void {
  if (import.meta.env.VITE_TRAFFIC_ANALYTICS_ENABLED !== "true") return;
  const load = () => {
    const script = document.createElement("script");
    script.src = "/traffic-collector.v1.js";
    script.async = true;
    script.dataset.site = IS_FORUM_SITE ? "forum" : "games";
    script.referrerPolicy = "no-referrer";
    document.head.append(script);
  };
  const schedule = () => {
    if (typeof window.requestIdleCallback === "function") window.requestIdleCallback(load, { timeout: 2000 });
    else window.setTimeout(load, 1000);
  };
  if (document.readyState === "complete") schedule();
  else window.addEventListener("load", schedule, { once: true });
}

/** 记录明确的游戏打开意图；只发送公开目录 slug，不表示游戏已加载或实际游玩。 */
export function recordGameOpenTraffic(slug: string): void {
  if (import.meta.env.VITE_TRAFFIC_ANALYTICS_ENABLED !== "true" || !/^[A-Za-z0-9_-]{1,80}$/.test(slug)) return;
  window.dispatchEvent(new CustomEvent("pl:traffic", {
    detail: { event_name: "game_open", path: `/games/${slug}` },
  }));
}
