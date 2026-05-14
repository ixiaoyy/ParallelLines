import type { BoardSummary } from "@/entities/board/model";
import type { PostItemVM } from "@/entities/post/model";
import type { TopicCardVM } from "@/entities/topic/model";

const now = Date.now();

const minutesAgo = (value: number) => new Date(now - 1000 * 60 * value).toISOString();
const hoursAgo = (value: number) => new Date(now - 1000 * 60 * 60 * value).toISOString();
const daysAgo = (value: number) => new Date(now - 1000 * 60 * 60 * 24 * value).toISOString();

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
    boardSlug: "announcements",
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
    lastPostedAt: minutesAgo(9),
    pinned: true,
    featured: true,
    status: "closed",
  },
  {
    id: "t-2",
    slug: "fastapi-background-job-queue",
    title: "FastAPI 长任务：先上队列还是 Celery？",
    boardSlug: "dev",
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
    lastPostedAt: minutesAgo(22),
    pinned: true,
    featured: true,
    unreadCount: 6,
    status: "open",
  },
  {
    id: "t-3",
    slug: "calm-tech-forum-design",
    title: "深色代码块太刺眼，有更稳的配色吗？",
    boardSlug: "plugins",
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
    lastPostedAt: hoursAgo(2),
    solved: true,
    status: "open",
  },
  {
    id: "t-4",
    slug: "openid-connect-group-sync",
    title: "OpenID Connect 组同步会不会误伤未同步用户组？",
    boardSlug: "support",
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
    lastPostedAt: hoursAgo(4),
    unreadCount: 2,
    status: "open",
  },
  {
    id: "t-5",
    slug: "testing-boosts-on-parallellines",
    title: "平行线的「助推」反馈机制应该怎么设计？",
    boardSlug: "community",
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
    lastPostedAt: hoursAgo(6),
    featured: true,
    status: "open",
  },
  {
    id: "t-6",
    slug: "category-rename-safe-path",
    title: "重命名旧版块时，slug、权限和历史链接需要一起迁移吗？",
    boardSlug: "support",
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
    lastPostedAt: hoursAgo(9),
    solved: true,
    status: "open",
  },
  {
    id: "t-7",
    slug: "markdown-copy-button-code-style",
    title: "Markdown 代码块需要复制按钮和行号吗？",
    boardSlug: "plugins",
    boardName: "插件与主题",
    boardColor: "var(--primary-hover)",
    authorName: "Ada",
    posterNames: ["Ada", "Moss", "Lina", "Noah"],
    tags: ["markdown", "代码块", "编辑器"],
    excerpt: "长帖排障时大家会反复复制命令，想把复制按钮、语言标识和行号做成统一的渲染组件。",
    replyCount: 24,
    viewCount: 4820,
    likeCount: 88,
    hotScore: 82,
    lastPostedAt: hoursAgo(12),
    featured: true,
    status: "open",
  },
  {
    id: "t-8",
    slug: "moderator-weekly-review-flow",
    title: "版主周报要不要公开处理摘要？",
    boardSlug: "community",
    boardName: "社区运营",
    boardColor: "var(--danger)",
    authorName: "Rui",
    posterNames: ["Rui", "Han", "May"],
    tags: ["版务", "透明度", "规则"],
    excerpt: "如果只公开数字缺少上下文，如果公开案例又可能暴露用户隐私，需要一个折中的站务摘要模板。",
    replyCount: 13,
    viewCount: 1740,
    likeCount: 35,
    hotScore: 63,
    lastPostedAt: daysAgo(1),
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

const fallbackPost = (topic: TopicCardVM): PostItemVM[] => [
  {
    id: `${topic.id}-p1`,
    floor: 1,
    authorName: topic.authorName,
    createdAt: topic.lastPostedAt,
    cookedHtml: `<p>${topic.excerpt}</p><p>这是一个用于前端联调的楼层流示例，后续会替换为 FastAPI 返回的 cooked HTML。</p>`,
    likeCount: topic.likeCount,
    replyCount: topic.replyCount,
  },
];

export const topicPostsById: Record<string, PostItemVM[]> = {
  "t-1": [
    {
      id: "t-1-p1",
      floor: 1,
      authorName: "平行线小助手",
      createdAt: hoursAgo(3),
      cookedHtml: `
        <p>今晚 22:00 后会把主题详情页和通知流合并到同一批接口契约里，发布入口会短暂进入只读。</p>
        <p>草稿保存在本地，不会被清空。迁移完成后未读数会重新按主题最后阅读楼层计算。</p>
      `.trim(),
      likeCount: 128,
      replyCount: 5,
    },
    {
      id: "t-1-p2",
      floor: 2,
      authorName: "Lina",
      createdAt: hoursAgo(2),
      cookedHtml: `
        <p>建议合并后在通知下拉里保留“只看提及我”的过滤，迁移期排查会很需要。</p>
        <pre><code>pnpm build:web
pnpm typecheck:web</code></pre>
      `.trim(),
      likeCount: 34,
      replyCount: 1,
    },
    {
      id: "t-1-p3",
      floor: 3,
      authorName: "Moss",
      createdAt: minutesAgo(24),
      cookedHtml: "<p>我关心的是楼层锚点是否会保持稳定，旧链接最好不要跳到主题顶部。</p>",
      likeCount: 19,
      replyCount: 0,
    },
  ],
  "t-2": [
    {
      id: "t-2-p1",
      floor: 1,
      authorName: "Lina",
      createdAt: hoursAgo(8),
      cookedHtml: `
        <p>我们现在有一个导入任务，用户上传 CSV 后最多会跑 30 秒。直接阻塞请求太脆，想先用轻量队列。</p>
        <p>我的疑问是：先做数据库任务表 + 后台 worker，还是直接上 Celery？</p>
      `.trim(),
      likeCount: 52,
      replyCount: 8,
    },
    {
      id: "t-2-p2",
      floor: 2,
      authorName: "Sam",
      createdAt: hoursAgo(6),
      cookedHtml: `
        <p>如果只有一个进程内 worker，部署重启时要先定义任务幂等键。可以把状态拆成 queued/running/succeeded/failed。</p>
        <pre><code>class ImportJobStatus(str, Enum):
    queued = "queued"
    running = "running"
    failed = "failed"</code></pre>
      `.trim(),
      likeCount: 41,
      replyCount: 3,
    },
    {
      id: "t-2-p3",
      floor: 3,
      authorName: "Moss",
      createdAt: hoursAgo(4),
      cookedHtml: "<p>先不要把重试次数藏在 worker 里，API 返回的任务详情应该能看到下一次重试时间。</p>",
      likeCount: 27,
      replyCount: 2,
    },
    {
      id: "t-2-p4",
      floor: 4,
      authorName: "Chen",
      createdAt: minutesAgo(42),
      cookedHtml: "<p>如果后面一定会上 Redis，先把队列接口抽成 service，具体实现可以从数据库轮询开始。</p>",
      likeCount: 18,
      replyCount: 0,
    },
  ],
  "t-3": [
    {
      id: "t-3-p1",
      floor: 1,
      authorName: "Moss",
      createdAt: hoursAgo(7),
      cookedHtml: `
        <p>白天模式下代码块从白卡片突然切到纯黑，会让长帖阅读有点断层。</p>
        <p>希望保留深色编辑器感，但边缘和阴影更柔和。</p>
      `.trim(),
      likeCount: 36,
      replyCount: 4,
    },
    {
      id: "t-3-p2",
      floor: 2,
      authorName: "Ada",
      createdAt: hoursAgo(3),
      cookedHtml: `
        <p>可以把代码块包一层标题栏，背景仍然用 <code>--code-bg</code>，标题栏稍微加一点蓝色透明度。</p>
        <pre><code>.markdown-body pre {
  background: var(--code-bg);
  color: var(--code-text);
}</code></pre>
      `.trim(),
      likeCount: 29,
      replyCount: 1,
    },
  ],
  "t-4": [
    {
      id: "t-4-p1",
      floor: 1,
      authorName: "Maarten",
      createdAt: hoursAgo(10),
      cookedHtml: "<p>一次 OIDC claim 变更后，用户被移出多个本地组。需要区分外部同步组与站内手动组。</p>",
      likeCount: 12,
      replyCount: 2,
    },
    {
      id: "t-4-p2",
      floor: 2,
      authorName: "Penar",
      createdAt: hoursAgo(5),
      cookedHtml: "<p>建议给外部同步组加 source 标记，手动组不要参与 OIDC 的全量覆盖。</p>",
      likeCount: 21,
      replyCount: 0,
    },
  ],
};

export function getBoardBySlug(slug: string) {
  return boards.find((board) => board.slug === slug);
}

export function getTopicsByBoardSlug(boardSlug: string) {
  return topics.filter((topic) => topic.boardSlug === boardSlug);
}

export function getTopicById(id: string) {
  return topics.find((topic) => topic.id === id);
}

export function getPostsByTopicId(topicId: string) {
  const topic = getTopicById(topicId);
  return topicPostsById[topicId] ?? (topic ? fallbackPost(topic) : []);
}

export function getRelatedTopics(topic: TopicCardVM) {
  return topics.filter((candidate) => candidate.boardSlug === topic.boardSlug && candidate.id !== topic.id).slice(0, 3);
}

export function readRouteParam(value: string | string[] | undefined) {
  if (Array.isArray(value)) {
    return value[0] ?? "";
  }

  return value ?? "";
}

export function getTopicByRoute(id: string | string[] | undefined, slug: string | string[] | undefined) {
  const routeId = readRouteParam(id);
  const routeSlug = readRouteParam(slug);
  return topics.find((topic) => topic.id === routeId && topic.slug === routeSlug) ?? getTopicById(routeId);
}
