import type { BoardSummary } from "@/entities/board/model";
import type { PostItemVM } from "@/entities/post/model";
import type { TopicCardVM } from "@/entities/topic/model";

const now = Date.now();

export const boards: BoardSummary[] = [
  {
    id: "b-frontend",
    slug: "frontend",
    name: "前端工程",
    description: "Vue、可访问性、设计系统与性能优化讨论。",
    color: "#3B82F6",
    topicCount: 1240,
    postCount: 9820,
    followerCount: 23100,
    isFollowing: true,
  },
  {
    id: "b-backend",
    slug: "backend",
    name: "后端架构",
    description: "FastAPI、数据库建模、异步任务与服务边界。",
    color: "#10B981",
    topicCount: 960,
    postCount: 7510,
    followerCount: 18400,
    isFollowing: false,
  },
];

export const topics: TopicCardVM[] = [
  {
    id: "t-1",
    slug: "fastapi-vue-forum-boundaries",
    title: "Vue 3 + FastAPI 的论坛项目，主题与楼层边界应该怎么切？",
    boardName: "后端架构",
    authorName: "Lina",
    tags: ["fastapi", "domain-model", "discourse"],
    excerpt: "把 Discourse 的 Topic/Post 拆法落到中文论坛语境：主题是聚合根，第一楼也是 Post。",
    replyCount: 42,
    viewCount: 8300,
    hotScore: 96,
    lastPostedAt: new Date(now - 1000 * 60 * 22).toISOString(),
    pinned: true,
    featured: true,
    status: "open",
  },
  {
    id: "t-2",
    slug: "calm-tech-forum-design",
    title: "浅灰背景和深色代码块能不能降低论坛阅读疲劳？",
    boardName: "前端工程",
    authorName: "Moss",
    tags: ["design-system", "a11y", "css"],
    excerpt: "尝试用 #F8F9FA 作为画布，用科技蓝承载行动，用极客绿表达状态和成功反馈。",
    replyCount: 18,
    viewCount: 2900,
    hotScore: 68,
    lastPostedAt: new Date(now - 1000 * 60 * 60 * 2).toISOString(),
    status: "open",
  },
];

export const highlightedPost: PostItemVM = {
  id: "p-1",
  floor: 1,
  authorName: "ParallelBot",
  createdAt: new Date(now - 1000 * 60 * 46).toISOString(),
  cookedHtml:
    "<p>服务端会保存 raw markdown 与 cooked HTML，并在渲染前完成净化。</p><pre><code>POST /api/v1/boards/frontend/topics</code></pre>",
  likeCount: 12,
  replyCount: 5,
};
