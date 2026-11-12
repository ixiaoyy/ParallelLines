// 各产品使用固定入口；论坛构建复用原业务源码，不把账号令牌带到其他站点。
export const SITE_LINKS = {
  games: "https://pingxingxian.space/",
  forum: "https://forum.pingxingxian.space/",
  tools: "https://tools.pingxingxian.space/",
  chat: "https://chat.pingxingxian.space/",
} as const;

export const IS_FORUM_SITE = import.meta.env.VITE_SITE_MODE === "forum";
