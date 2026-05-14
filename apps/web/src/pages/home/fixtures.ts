import type { BoardSummary } from "@/entities/board/model";
import type { TopicCardVM } from "@/entities/topic/model";

const now = Date.now();

export interface DiscoveryTab {
  key: "latest" | "top" | "categories" | "hot" | "votes";
  label: string;
  description: string;
}

export interface HomeMetric {
  label: string;
  value: string;
  trend: string;
}

export interface SidebarLink {
  title: string;
  meta: string;
}

export const discoveryTabs: DiscoveryTab[] = [
  { key: "latest", label: "Latest", description: "按最后活跃时间排列" },
  { key: "top", label: "Top", description: "社区近期高质量讨论" },
  { key: "categories", label: "Categories", description: "按版块语义聚合" },
  { key: "hot", label: "Hot", description: "回复、浏览与收藏加权" },
  { key: "votes", label: "Votes", description: "产品反馈与投票主题" },
];

export const homeMetrics: HomeMetric[] = [
  { label: "今日主题", value: "128", trend: "+18%" },
  { label: "在线成员", value: "2.4k", trend: "追踪中" },
  { label: "已解决", value: "86", trend: "本周" },
];

export const boards: BoardSummary[] = [
  {
    id: "b-announcements",
    slug: "announcements",
    name: "公告与发布",
    description: "版本节奏、站务公告、社区路线图与治理说明。",
    color: "var(--primary)",
    topicCount: 248,
    postCount: 3140,
    followerCount: 28600,
    isFollowing: true,
  },
  {
    id: "b-support",
    slug: "support",
    name: "支持与排障",
    description: "安装、升级、报错定位，以及可复现问题的协作排查。",
    color: "var(--accent-geek)",
    topicCount: 1520,
    postCount: 14890,
    followerCount: 35100,
    isFollowing: true,
  },
  {
    id: "b-dev",
    slug: "dev",
    name: "开发与 API",
    description: "FastAPI、Vue、OpenAPI、权限模型与扩展开发讨论。",
    color: "var(--warning)",
    topicCount: 986,
    postCount: 9970,
    followerCount: 22600,
    isFollowing: false,
  },
  {
    id: "b-plugins",
    slug: "plugins",
    name: "插件与主题",
    description: "组件扩展、主题定制、编辑器体验与社区插件共创。",
    color: "var(--primary-hover)",
    topicCount: 632,
    postCount: 5460,
    followerCount: 17400,
    isFollowing: false,
  },
  {
    id: "b-community",
    slug: "community",
    name: "社区运营",
    description: "版主管理、内容安全、规则共识与增长实验。",
    color: "var(--danger)",
    topicCount: 410,
    postCount: 3880,
    followerCount: 11900,
    isFollowing: false,
  },
];

export const topics: TopicCardVM[] = [
  {
    id: "t-1",
    slug: "new-to-parallellines-start-here",
    title: "New to ParallelLines? Start here!",
    boardName: "公告与发布",
    boardColor: "var(--primary)",
    authorName: "ParallelBot",
    posterNames: ["ParallelBot", "Lina", "Moss", "Kai"],
    tags: ["guidelines", "onboarding"],
    excerpt: "欢迎来到 ParallelLines：这里会集中解释版块、主题、楼层、通知级别，以及如何写出高质量提问。",
    replyCount: 5,
    viewCount: 115032,
    likeCount: 429,
    hotScore: 99,
    lastPostedAt: new Date(now - 1000 * 60 * 9).toISOString(),
    pinned: true,
    featured: true,
    status: "closed",
  },
  {
    id: "t-2",
    slug: "fastapi-vue-forum-boundaries",
    title: "Vue 3 + FastAPI 的论坛项目，主题与楼层边界应该怎么切？",
    boardName: "开发与 API",
    boardColor: "var(--warning)",
    authorName: "Lina",
    posterNames: ["Lina", "Sam", "Moss", "Chen", "Echo"],
    tags: ["fastapi", "domain-model", "discourse"],
    excerpt: "把 Discourse 的 Topic/Post 拆法落到中文论坛语境：主题是聚合根，第一楼也是 Post。",
    replyCount: 42,
    viewCount: 8300,
    likeCount: 92,
    hotScore: 96,
    lastPostedAt: new Date(now - 1000 * 60 * 22).toISOString(),
    pinned: true,
    featured: true,
    unreadCount: 6,
    status: "open",
  },
  {
    id: "t-3",
    slug: "calm-tech-forum-design",
    title: "浅灰背景和深色代码块能不能降低论坛阅读疲劳？",
    boardName: "插件与主题",
    boardColor: "var(--primary-hover)",
    authorName: "Moss",
    posterNames: ["Moss", "Ada", "Yun"],
    tags: ["design-system", "a11y", "css"],
    excerpt: "尝试用浅灰画布承载长期阅读，用科技蓝标记行动，用极客绿表达状态和成功反馈。",
    replyCount: 18,
    viewCount: 2900,
    likeCount: 61,
    hotScore: 68,
    lastPostedAt: new Date(now - 1000 * 60 * 60 * 2).toISOString(),
    solved: true,
    status: "open",
  },
  {
    id: "t-4",
    slug: "openid-connect-group-sync",
    title: "OpenID Connect 组同步会不会误伤未同步用户组？",
    boardName: "支持与排障",
    boardColor: "var(--accent-geek)",
    authorName: "Maarten",
    posterNames: ["Maarten", "Penar", "Kai", "Lilly"],
    tags: ["sso", "openid-connect", "bug"],
    excerpt: "一次 OIDC claim 变更后，用户被移出多个本地组。需要区分外部同步组与站内手动组。",
    replyCount: 7,
    viewCount: 1290,
    likeCount: 23,
    hotScore: 74,
    lastPostedAt: new Date(now - 1000 * 60 * 60 * 4).toISOString(),
    unreadCount: 2,
    status: "open",
  },
  {
    id: "t-5",
    slug: "testing-boosts-on-parallellines",
    title: "Testing Boosts on ParallelLines",
    boardName: "社区运营",
    boardColor: "var(--danger)",
    authorName: "Keegan",
    posterNames: ["Keegan", "Dylan", "Rui", "Han", "May", "Noah"],
    tags: ["reactions", "votes", "experiment"],
    excerpt: "Boosts 介于点赞和完整回复之间，适合表达“这个建议值得被更多人看到”。",
    replyCount: 78,
    viewCount: 14600,
    likeCount: 310,
    hotScore: 91,
    lastPostedAt: new Date(now - 1000 * 60 * 60 * 6).toISOString(),
    featured: true,
    status: "open",
  },
  {
    id: "t-6",
    slug: "category-rename-safe-path",
    title: "重命名旧版块时，slug、权限和历史链接需要一起迁移吗？",
    boardName: "支持与排障",
    boardColor: "var(--accent-geek)",
    authorName: "Bayardo",
    posterNames: ["Bayardo", "Putty", "Lilly"],
    tags: ["categories", "migration"],
    excerpt: "版块名调整是组织结构变化的常见操作，应该让主题依赖稳定 ID，而不是可变 slug。",
    replyCount: 6,
    viewCount: 640,
    likeCount: 18,
    hotScore: 55,
    lastPostedAt: new Date(now - 1000 * 60 * 60 * 9).toISOString(),
    solved: true,
    status: "open",
  },
];

export const sidebarLinks: SidebarLink[] = [
  { title: "如何写一个可复现的 Bug 主题", meta: "排障指南 · 6 min read" },
  { title: "版块通知级别：Watching / Tracking / Normal", meta: "社区规则 · 4 min read" },
  { title: "Markdown 与代码块的安全渲染边界", meta: "开发指南 · 8 min read" },
];

export const tagCloud = [
  "fastapi",
  "vue3",
  "openapi",
  "sso",
  "moderation",
  "composer",
  "search",
  "votes",
  "plugins",
];
