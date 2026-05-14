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
  { key: "latest", label: "最新", description: "刚被回复过的主题" },
  { key: "top", label: "优质", description: "最近被反复收藏的答案" },
  { key: "categories", label: "版块", description: "按问题归属聚合" },
  { key: "hot", label: "热门", description: "回复、浏览与收藏都在上涨" },
  { key: "votes", label: "投票", description: "正在等待社区表态" },
];

export const homeMetrics: HomeMetric[] = [
  { label: "今日新帖", value: "128", trend: "+18%" },
  { label: "正在编辑", value: "37", trend: "实时" },
  { label: "本周已解决", value: "86", trend: "已标记" },
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
    slug: "v01-topic-detail-notification-merge",
    title: "v0.1 发布：主题详情页和通知流今晚合并",
    boardName: "公告与发布",
    boardColor: "var(--primary)",
    authorName: "平行线小助手",
    posterNames: ["平行线小助手", "Lina", "Moss", "Kai"],
    tags: ["发布", "通知"],
    excerpt: "今晚会短暂冻结发布主题入口，已有草稿不受影响。通知未读数会在迁移后重新计算。",
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
    slug: "fastapi-background-job-queue",
    title: "FastAPI 长任务：先上队列还是 Celery？",
    boardName: "开发与 API",
    boardColor: "var(--warning)",
    authorName: "Lina",
    posterNames: ["Lina", "Sam", "Moss", "Chen", "Echo"],
    tags: ["fastapi", "队列", "架构"],
    excerpt: "导入任务超过 30 秒后用户一直等在页面上，想先拆成轻量队列，不确定会不会把失败重试搞复杂。",
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
    title: "深色代码块太刺眼，有更稳的配色吗？",
    boardName: "插件与主题",
    boardColor: "var(--primary-hover)",
    authorName: "Moss",
    posterNames: ["Moss", "Ada", "Yun"],
    tags: ["设计系统", "无障碍", "css"],
    excerpt: "白天模式下代码块对比太强，想保留语法高亮，同时减少长贴阅读时的视觉跳变。",
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
    tags: ["单点登录", "openid-connect", "缺陷"],
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
    title: "平行线的「助推」反馈机制应该怎么设计？",
    boardName: "社区运营",
    boardColor: "var(--danger)",
    authorName: "Keegan",
    posterNames: ["Keegan", "Dylan", "Rui", "Han", "May", "Noah"],
    tags: ["互动反馈", "投票", "实验"],
    excerpt: "助推介于点赞和完整回复之间，适合表达“这个建议值得被更多人看到”。",
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
    tags: ["版块", "迁移"],
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
  { title: "登录回跳首页只在 Edge 复现，已有 4 人确认", meta: "支持与排障 · 18 分钟前" },
  { title: "主题被合并后收藏还应该保留原入口吗？", meta: "社区运营 · 32 分钟前" },
  { title: "OpenAPI client 生成后枚举命名不稳定", meta: "开发与 API · 1 小时前" },
];

export const tagCloud = [
  "fastapi",
  "vue3",
  "openapi",
  "单点登录",
  "内容审核",
  "编辑器",
  "搜索",
  "投票",
  "插件",
];
