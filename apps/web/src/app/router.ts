import { createRouter, createWebHistory } from "vue-router";
import type { RouteLocationNormalized } from "vue-router";

import { fetchCurrentUser } from "@/features/auth/api";
import { CURRENT_USER_STALE_TIME_MS, type UserPublic } from "@/features/auth/model";
import { canAccessModeration, isAdmin } from "@/features/auth/permissions";
import { clearAuthTokens, hasAccessToken, isAuthenticationError } from "@/shared/api/client";
import { queryClient } from "@/shared/api/queryClient";
import { queryKeys } from "@/shared/api/queryKeys";
import { readRouteParam } from "@/shared/router/params";
import type { RouteSeoMeta } from "@/shared/seo/meta";

type RequiredAccess = "authenticated" | "admin" | "moderation";
const NOINDEX_ROBOTS = "noindex,nofollow";
const HASH_SCROLL_RETRY_LIMIT = 40;
const HASH_SCROLL_RETRY_DELAY_MS = 50;

declare module "vue-router" {
  interface RouteMeta {
    requiredAccess?: RequiredAccess;
    forumShell?: boolean;
    seo?: RouteSeoMeta;
  }
}

export const router = createRouter({
  history: createWebHistory(),
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) {
      return savedPosition;
    }
    // 切换公式教程时由页面定位正文，保留该工具的目录选择和阅读位置。
    if (to.name === "tool-excel-formulas" && from.name === "tool-excel-formulas") {
      return false;
    }
    // 分享或刷新具体教程时等待正文出现再定位；无课题参数的工具入口仍从顶部开始。
    if (to.name === "tool-excel-formulas" && typeof to.query.lesson === "string" && to.query.lesson) {
      return waitForHashTarget("#lesson-title").then((found) => {
        // 等待期间已经离开该教程时，不再改变后来页面的阅读位置。
        if (router.currentRoute.value.fullPath !== to.fullPath) return false;
        return found ? { el: "#lesson-title", top: 24, left: 0 } : { top: 0, left: 0 };
      });
    }
    // 版块目录只切换筛选时保持位置，通知楼层链接等待异步内容出现后定位。
    if (to.name === "board-directory" && from.name === "board-directory") {
      return false;
    }
    if (to.meta.forumShell && to.hash) {
      return waitForHashTarget(to.hash).then((found) =>
        found ? { el: to.hash, top: 0, left: 0, behavior: "smooth" } : { top: 0, left: 0 },
      );
    }
    return { top: 0, left: 0 };
  },
  routes: [
    {
      path: "/",
      alias: "/games",
      name: "home",
      component: () => import("@/pages/catalog/CatalogHomePage.vue"),
      meta: {
        seo: {
          title: "AI 游戏 · GPT / Claude Code / Kimi · 点开即玩 | {siteName}",
          description: "{siteName} 收录 AI 网页游戏，探索 GPT、Claude Code、Kimi 等工具带来的游戏创意。涵盖策略、卡牌、解谜、角色扮演与休闲玩法，按分类和热度发现游戏，点开即玩。",
          canonicalPath: "/",
        },
      },
    },
    {
      path: "/play/generals-soldiers",
      name: "play-generals-soldiers",
      component: () => import("@/pages/play/GeneralsSoldiersPage.vue"),
      meta: {
        seo: {
          title: "将军战小兵 · {siteTitle}",
          description: "在平行线与电脑进行将军战小兵对弈。",
          canonicalPath: "/play/generals-soldiers",
        },
      },
    },
    // 新小游戏独立按需加载，目录入口仍复用首页和既有统计。
    {
      path: "/play/snake-escape",
      name: "play-snake-escape",
      component: () => import("@/pages/play/SnakeEscapePage.vue"),
      meta: {
        seo: {
          title: "蛇蛇出洞 · {siteTitle}",
          description: "按顺序放走彩色小蛇，避开阻挡，在倒计时结束前清空棋盘。",
          canonicalPath: "/play/snake-escape",
        },
      },
    },
    {
      path: "/play/flappy-dunk",
      name: "play-flappy-dunk",
      component: () => import("@/pages/play/FlappyDunkPage.vue"),
      meta: {
        seo: {
          title: "飞翼灌篮 · {siteTitle}",
          description: "点按让带翅膀的篮球跳跃，从上方穿过篮圈，挑战连续进球和最高分。",
          canonicalPath: "/play/flappy-dunk",
        },
      },
    },
    {
      path: "/tools",
      name: "tools",
      component: () => import("@/pages/tools/ToolsPage.vue"),
      meta: {
        seo: {
          title: "工具 · {siteTitle}",
          description: "文职常用公式，按步骤照着做。",
          canonicalPath: "/tools",
        },
      },
    },
    // Excel 教程独立加载，便于从工具列表打开完整内容。
    {
      path: "/tools/excel-formulas",
      name: "tool-excel-formulas",
      component: () => import("@/pages/tools/ExcelFormulaPage.vue"),
      meta: {
        seo: {
          title: "Excel 公式速查 · {siteTitle}",
          description: "文职常用公式，按步骤照着做。",
          canonicalPath: "/tools/excel-formulas",
        },
      },
    },
    // 拼豆工具独立加载，图片生成与编辑在浏览器本地完成。
    {
      path: "/tools/bead-pattern",
      name: "tool-bead-pattern",
      component: () => import("@/pages/tools/BeadPatternPage.vue"),
      meta: {
        seo: {
          title: "拼豆图纸生成器 · {siteTitle}",
          description: "将图片转换为拼豆图纸，查看色号和用量。",
          canonicalPath: "/tools/bead-pattern",
        },
      },
    },
    // 旧论坛地址继续保留；主导航中的圈子暂未开放。
    {
      path: "/forum",
      name: "forum-home",
      component: () => import("@/pages/home/HomePage.vue"),
      meta: {
        forumShell: true,
        seo: {
          title: "{siteName}",
          description: "{siteName}：{siteTagline}。浏览公开版块与可追溯讨论。",
          canonicalPath: "/forum",
        },
      },
    },
    {
      path: "/boards",
      name: "board-directory",
      component: () => import("@/pages/board/BoardDirectoryPage.vue"),
      meta: {
        forumShell: true,
        seo: {
          title: "全部版块 · {siteTitle}",
          description: "浏览{siteTitle}的公开版块、最新主题和可追溯讨论。",
          canonicalPath: "/boards",
        },
      },
    },
    {
      path: "/forbidden",
      name: "access-denied",
      component: () => import("@/pages/auth/AccessDeniedPage.vue"),
      meta: {
        forumShell: true,
        seo: {
          title: "无权限 · {siteTitle}",
          description: "当前账号没有访问该页面所需的权限。",
          canonicalPath: "/forbidden",
          robots: NOINDEX_ROBOTS,
        },
      },
    },
    {
      path: "/account",
      name: "account-home",
      component: () => import("@/pages/user/UserProfilePage.vue"),
      meta: {
        forumShell: true,
        requiredAccess: "authenticated",
        seo: {
          title: "个人中心 · {siteTitle}",
          description: "查看自己的讨论、资料、成长和账号设置。",
          canonicalPath: "/account",
          robots: NOINDEX_ROBOTS,
        },
      },
    },
    {
      path: "/account/profile",
      name: "account-profile",
      component: () => import("@/pages/user/UserProfilePage.vue"),
      meta: {
        forumShell: true,
        requiredAccess: "authenticated",
        seo: {
          title: "资料设置 · {siteTitle}",
          description: "管理平行线公开资料、头像、简介和个人偏好。",
          canonicalPath: "/account/profile",
          robots: NOINDEX_ROBOTS,
        },
      },
    },
    {
      path: "/account/settings",
      name: "account-settings",
      component: () => import("@/pages/user/UserProfilePage.vue"),
      meta: {
        forumShell: true,
        requiredAccess: "authenticated",
        seo: {
          title: "账号设置 · {siteTitle}",
          description: "管理平行线账号密码和登录邮箱。",
          canonicalPath: "/account/settings",
          robots: NOINDEX_ROBOTS,
        },
      },
    },
    {
      path: "/account/preferences",
      name: "account-preferences",
      component: () => import("@/pages/email/EmailPreferencesPage.vue"),
      meta: {
        forumShell: true,
        requiredAccess: "authenticated",
        seo: {
          title: "偏好设置 · {siteTitle}",
          description: "管理平行线邮件通知、摘要和订阅偏好。",
          canonicalPath: "/account/preferences",
          robots: NOINDEX_ROBOTS,
        },
      },
    },
    {
      path: "/me",
      redirect: { name: "account-home" },
    },
    {
      path: "/members/:id",
      name: "user-profile",
      component: () => import("@/pages/user/UserProfilePage.vue"),
      meta: {
        forumShell: true,
        seo: {
          title: "用户档案 · {siteTitle}",
          description: "查看平行线成员的公开资料、主题和社区活动。",
        },
      },
    },
    {
      path: "/users",
      name: "user-directory",
      component: () => import("@/pages/user/UserDirectoryPage.vue"),
      meta: {
        forumShell: true,
        seo: {
          title: "成员 · {siteTitle}",
          description: "浏览平行线社区成员，发现活跃作者和公开讨论贡献。",
          canonicalPath: "/users",
        },
      },
    },
    {
      path: "/b/:slug",
      name: "board-detail",
      component: () => import("@/pages/board/BoardPage.vue"),
      meta: {
        forumShell: true,
        seo: {
          title: "版块详情 · {siteTitle}",
          description: "查看平行线版块下的最新主题、热门讨论和精华内容。",
        },
      },
    },
    {
      path: "/new-topic",
      name: "new-topic",
      component: () => import("@/pages/topic/NewTopicPage.vue"),
      meta: {
        forumShell: true,
        requiredAccess: "authenticated",
        seo: {
          title: "发布主题 · {siteTitle}",
          description: "在平行线选择版块并发布新的公开讨论主题。",
          canonicalPath: "/new-topic",
          robots: NOINDEX_ROBOTS,
        },
      },
    },
    {
      path: "/invites",
      name: "my-invites",
      component: () => import("@/pages/invites/MyInvitesPage.vue"),
      meta: {
        forumShell: true,
        requiredAccess: "authenticated",
        seo: {
          title: "邀请 · {siteTitle}",
          description: "管理平行线账号邀请记录和邀请链接。",
          canonicalPath: "/invites",
          robots: NOINDEX_ROBOTS,
        },
      },
    },
    {
      path: "/email-preferences",
      redirect: { name: "account-preferences" },
    },
    {
      path: "/messages",
      name: "messages",
      component: () => import("@/pages/messages/MessagesPage.vue"),
      meta: {
        forumShell: true,
        requiredAccess: "authenticated",
        seo: {
          title: "私信 · {siteTitle}",
          description: "查看和管理平行线站内私信对话。",
          canonicalPath: "/messages",
          robots: NOINDEX_ROBOTS,
        },
      },
    },
    {
      path: "/events",
      name: "events",
      component: () => import("@/pages/events/EventsPage.vue"),
      meta: {
        forumShell: true,
        seo: {
          title: "活动 · {siteTitle}",
          description: "查看平行线社区活动、订阅日历并跟进公开事件安排。",
          canonicalPath: "/events",
        },
      },
    },
    {
      path: "/moderation/reviewables",
      name: "my-reviewables",
      component: () => import("@/pages/moderation/MyReviewablesPage.vue"),
      meta: {
        forumShell: true,
        requiredAccess: "authenticated",
        seo: {
          title: "我的审核 · {siteTitle}",
          description: "查看分配给当前账号的平行线待处理审核事项。",
          canonicalPath: "/moderation/reviewables",
          robots: NOINDEX_ROBOTS,
        },
      },
    },
    {
      path: "/search",
      name: "search",
      component: () => import("@/pages/search/SearchPage.vue"),
      meta: {
        forumShell: true,
        seo: {
          title: "搜索 · {siteTitle}",
          description: "搜索平行线公开主题、标签和作者，快速定位可追溯讨论。",
          canonicalPath: "/search",
          robots: "noindex,follow",
        },
      },
    },
    {
      path: "/admin/analytics",
      name: "admin-analytics",
      component: () => import("@/pages/admin/AdminAnalyticsPage.vue"),
      meta: {
        forumShell: true,
        requiredAccess: "admin",
        seo: {
          title: "访问与用户增长 · {siteTitle}",
          description: "查看平行线访问表现、真实用户增长、来源渠道和入口页统计。",
          canonicalPath: "/admin/analytics",
          robots: NOINDEX_ROBOTS,
        },
      },
    },
    {
      path: "/admin/users",
      name: "admin-users",
      component: () => import("@/pages/admin/AdminUsersPage.vue"),
      meta: {
        forumShell: true,
        requiredAccess: "admin",
        seo: {
          title: "用户管理 · {siteTitle}",
          description: "管理平行线用户角色、状态、等级和徽章。",
          canonicalPath: "/admin/users",
          robots: NOINDEX_ROBOTS,
        },
      },
    },
    {
      path: "/admin/system",
      name: "admin-system",
      component: () => import("@/pages/admin/AdminSystemPage.vue"),
      meta: {
        forumShell: true,
        requiredAccess: "admin",
        seo: {
          title: "系统运行 · {siteTitle}",
          description: "查看平行线核心服务、后台任务、邮件和审计运行状态。",
          canonicalPath: "/admin/system",
          robots: NOINDEX_ROBOTS,
        },
      },
    },
    {
      path: "/admin/moderation",
      name: "admin-moderation",
      component: () => import("@/pages/admin/ModerationPage.vue"),
      meta: {
        forumShell: true,
        requiredAccess: "moderation",
        seo: {
          title: "审核后台 · {siteTitle}",
          description: "处理平行线内容审核、举报和隐藏恢复记录。",
          canonicalPath: "/admin/moderation",
          robots: NOINDEX_ROBOTS,
        },
      },
    },
    {
      path: "/t/:slug/:id",
      redirect: (to) => ({
        name: "topic-detail",
        params: {
          id: readRouteParam(to.params.id),
          slug: readRouteParam(to.params.slug),
        },
        query: to.query,
        hash: to.hash,
      }),
    },
    {
      path: "/topics/:id/:slug?",
      name: "topic-detail",
      component: () => import("@/pages/topic/TopicDetailPage.vue"),
      meta: {
        forumShell: true,
        seo: {
          title: "主题详情 · {siteTitle}",
          description: "查看平行线公开主题详情、楼层回复和可追溯讨论上下文。",
          ogType: "article",
        },
      },
    },
    {
      path: "/play",
      name: "play-hub",
      redirect: { name: "home" },
    },
    {
      path: "/auth/chat",
      name: "chat-sso",
      component: () => import("@/pages/auth/ChatSsoPage.vue"),
      meta: {
        forumShell: false,
        seo: { title: "进入聊天 · {siteTitle}", robots: "noindex,nofollow" },
      },
    },
    {
      path: "/auth",
      name: "auth",
      component: () => import("@/pages/auth/AuthPage.vue"),
      meta: {
        forumShell: true,
        seo: {
          title: "登录注册 · {siteTitle}",
          description: "登录或注册平行线账号，继续发布主题、回复讨论和管理个人资料。",
          canonicalPath: "/auth",
          robots: "noindex,nofollow",
        },
      },
    },
    {
      path: "/admin",
      name: "admin-dashboard",
      component: () => import("@/pages/admin/CatalogAdminPage.vue"),
      meta: {
        requiredAccess: "admin",
        seo: {
          title: "目录管理与访问统计 · {siteTitle}",
          description: "管理平行线项目目录并查看访问统计。",
          canonicalPath: "/admin",
          robots: "noindex,nofollow",
        },
      },
    },
    {
      path: "/admin/forum",
      name: "forum-admin-dashboard",
      component: () => import("@/pages/admin/AdminDashboardPage.vue"),
      meta: {
        forumShell: true,
        requiredAccess: "admin",
        seo: {
          title: "后台 · {siteTitle}",
          description: "查看平行线访问统计、用户管理、内容安全和系统状态。",
          canonicalPath: "/admin/forum",
          robots: NOINDEX_ROBOTS,
        },
      },
    },
    {
      path: "/admin/:pathMatch(.*)*",
      redirect: { name: "admin-dashboard" },
    },
    {
      path: "/:pathMatch(.*)*",
      redirect: { name: "home" },
    },
  ],
});

router.beforeEach(async (to) => {
  const requiredAccess = to.meta.requiredAccess;
  if (!requiredAccess) {
    return true;
  }

  // 所有受保护论坛入口复用当前账号缓存；未登录时保留完整回跳地址。
  const currentUser = await loadCurrentUserForRoute();
  if (!currentUser) {
    return { name: "auth", query: { redirect: to.fullPath } };
  }
  if (requiredAccess === "admin" && !isAdmin(currentUser)) {
    // 目录后台保留原有无权限回目录行为，论坛管理页使用已有权限说明页。
    return to.name === "admin-dashboard" ? { name: "home" } : accessDeniedRedirect(to, "admin");
  }
  if (requiredAccess === "moderation" && !canAccessModeration(currentUser)) {
    return accessDeniedRedirect(to, "moderation");
  }
  return true;
});

async function loadCurrentUserForRoute(): Promise<UserPublic | null> {
  if (!hasAccessToken()) {
    return null;
  }

  const cachedUser = queryClient.getQueryData<UserPublic | null>(queryKeys.currentUser);
  const cachedState = queryClient.getQueryState(queryKeys.currentUser);
  if (
    cachedUser &&
    cachedState?.dataUpdatedAt &&
    Date.now() - cachedState.dataUpdatedAt < CURRENT_USER_STALE_TIME_MS
  ) {
    return cachedUser;
  }

  try {
    return await queryClient.fetchQuery({
      queryKey: queryKeys.currentUser,
      queryFn: fetchCurrentUser,
      retry: false,
      staleTime: CURRENT_USER_STALE_TIME_MS,
    });
  } catch (error) {
    if (isAuthenticationError(error)) {
      clearAuthTokens();
      queryClient.setQueryData(queryKeys.currentUser, null);
      return null;
    }
    return queryClient.getQueryData<UserPublic | null>(queryKeys.currentUser) ?? null;
  }
}

// 将缺少权限的论坛请求交给现有权限页；to 为被拒绝路由，requiredAccess 为所需权限，返回保留来源的路由目标。
function accessDeniedRedirect(to: RouteLocationNormalized, requiredAccess: RequiredAccess) {
  return {
    name: "access-denied",
    query: { required: requiredAccess, from: to.fullPath },
  };
}

// 等待路由对应的异步内容；hash 为目标片段，最多等待两秒，返回目标元素是否已出现。
function waitForHashTarget(hash: string): Promise<boolean> {
  if (typeof document === "undefined") {
    return Promise.resolve(false);
  }
  return new Promise((resolve) => {
    let attempts = 0;
    const checkTarget = () => {
      // URL 片段可能不是有效选择器，异常时按目标尚未出现处理。
      try {
        if (document.querySelector(hash)) {
          resolve(true);
          return;
        }
      } catch {
        resolve(false);
        return;
      }
      attempts += 1;
      if (attempts >= HASH_SCROLL_RETRY_LIMIT) {
        resolve(false);
        return;
      }
      window.setTimeout(checkTarget, HASH_SCROLL_RETRY_DELAY_MS);
    };
    checkTarget();
  });
}
