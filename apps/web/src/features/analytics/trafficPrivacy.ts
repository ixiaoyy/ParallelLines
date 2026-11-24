const EXCLUDE_COOKIE_NAME = "px_traffic_exclude";
const SHARED_DOMAIN = "pingxingxian.space";

/** 读取当前浏览器的统计排除偏好；Cookie 不可读时不假定已成功排除。 */
export function isTrafficExcluded(): boolean {
  try {
    return document.cookie.split(";").some((cookie) => cookie.trim() === `${EXCLUDE_COOKIE_NAME}=1`);
  } catch {
    return false;
  }
}

/** 写入匿名统计排除偏好并通知本页采集器；只影响当前浏览器，不改变任何账号或全局配置。 */
export function setTrafficExcluded(excluded: boolean): boolean {
  try {
    const host = window.location.hostname.toLowerCase();
    const shared = host === SHARED_DOMAIN || host.endsWith(`.${SHARED_DOMAIN}`);
    const domain = shared ? `; Domain=.${SHARED_DOMAIN}` : "";
    const secure = window.location.protocol === "https:" ? "; Secure" : "";
    const maxAge = excluded ? 365 * 24 * 60 * 60 : 0;
    document.cookie = `${EXCLUDE_COOKIE_NAME}=${excluded ? "1" : ""}; Path=/; Max-Age=${maxAge}; SameSite=Lax${domain}${secure}`;
    const saved = isTrafficExcluded() === excluded;
    if (saved) {
      window.dispatchEvent(new CustomEvent("pl:traffic-preference", { detail: { excluded } }));
    }
    return saved;
  } catch {
    return false;
  }
}
