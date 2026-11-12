import type { Page } from "@playwright/test";

import type { UserPublic } from "../../../src/features/auth/model";
import type { BoardResponse } from "../../../src/features/boards/model";
import type { PostResponse } from "../../../src/features/posts/model";
import type { TopicResponse } from "../../../src/features/topics/model";

const NOW = "2026-10-19T08:00:00Z";
export const USER: UserPublic = {
  id: "101", username: "forum_fixture", email: "forum-fixture@example.com", avatar_url: null,
  display_name: null, bio: null, website_url: null, location: null, role: "user", level: 1,
  trust_level: 1, trust_level_label: "基础成员", points_balance: 0, experience_total: 50,
  experience_to_next_level: 100, level_progress_percent: 0, status: "active",
  two_factor_enabled: false, profile_visibility: "public", show_activity: true,
  interface_theme: "colorful", locale: "zh-CN", created_at: NOW,
};
const BOARD: BoardResponse = {
  id: "10", slug: "lounge", name: "闲聊", description: "论坛入口回归固定数据。",
  color: "#409EFF", avatar_url: null, owner_id: null, parent_board_id: null,
  parent_board_slug: null, parent_board_name: null, visibility: "public", required_tags: [],
  allowed_tags: [], post_template: null, default_notification_level: "normal", default_sort: "latest",
  topic_count: 1, post_count: 1, follower_count: 0, is_following: false,
  notification_level: null, can_create_topic: true, created_at: NOW, updated_at: NOW,
};
export const TOPIC: TopicResponse = {
  id: "201", slug: "forum-entry", title: "恢复论坛入口的固定主题", board_id: "10",
  board_slug: "lounge", board_name: "闲聊", board_color: "#409EFF", board_visibility: "public",
  author_id: "101", author_name: USER.username, author_avatar_url: null, author_role: "user",
  author_is_persona: false, author_persona_kind: null, author_level: 1, author_trust_level: 1,
  author_trust_level_label: "基础成员", tags: [], accepted_answer_post_id: null,
  solved_at: null, solved_by_id: null, answer_mode: false, vote_score: 0, vote_count: 0,
  my_vote: 0, poll: null, topic_type: "regular", visibility: "public", status: "open",
  pinned: false, featured: false, view_count: 1, reply_count: 0, like_count: 0, hot_score: 1,
  last_posted_at: NOW, created_at: NOW, updated_at: NOW, merged_into_topic_id: null,
  share_url: "/topics/201/forum-entry", excerpt: "入口恢复后的固定正文。",
};

/** 生成明确归属的模拟回复；测试不会连接数据库或向真实论坛写入。 */
function post(number: number, body: string): PostResponse {
  return {
    id: String(300 + number), topic_id: TOPIC.id, user_id: USER.id, author_name: USER.username,
    author_avatar_url: null, author_role: "user", author_is_persona: false, author_persona_kind: null,
    author_level: 1, author_trust_level: 1, author_trust_level_label: "基础成员", parent_id: null,
    post_number: number, raw_md: body, cooked_html: `<p>${body}</p>`, reply_count: 0, like_count: 0,
    accepted_answer: false, vote_score: 0, vote_count: 0, my_vote: 0,
    share_url: `${TOPIC.share_url}#post-${number}`, deleted_at: null, created_at: NOW, updated_at: NOW,
  };
}

/** 拦截全部业务接口，记录真实页面提交的参数，并阻止站外请求。 */
export async function fixture(page: Page, role?: "user" | "admin") {
  const state = {
    errors: [] as string[], unexpected: [] as string[], requested: [] as string[],
    writes: [] as { path: string; data: unknown }[],
    topic: { ...TOPIC }, posts: [post(1, "入口恢复后的固定正文。")],
  };
  const user = { ...USER, role: role ?? "user" };
  if (role) {
    await page.addInitScript(() => localStorage.setItem("parallellines.access_token", "fixture-only"));
  }
  page.on("pageerror", (error) => state.errors.push(error.message));
  await page.route("**/*", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (!url.pathname.startsWith("/api/")) {
      const localOrigin = new URL(process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5173").origin;
      return url.origin === localOrigin ? route.continue() : route.abort();
    }
    const path = url.pathname.replace(/^\/api\/v1/, "");
    const method = request.method();
    state.requested.push(`${method} ${path}`);
    const send = (data: unknown) => route.fulfill({ json: { data } });
    if (path === "/site/settings") {
      return send({ settings: { site_title: "平行线", site_tagline: "固定数据验证", brand_primary_color: "#d946ef" }, updated_at: null });
    }
    if (path === "/site/visits") return send({ recorded: false });
    // 目录默认页已使用公开概览；空目录替身仍保留该真实响应结构。
    if (path === "/catalog/overview") return send({ categories: [], hero: { projects: [], total: 0, next_offset: null } });
    if (path === "/catalog" || path === "/admin/catalog") return send({ categories: [] });
    if (path === "/admin/analytics") return send({ totals: { page_views: 0, unique_visitors: 0, external_referrals: 0 }, traffic_sources: [], entry_pages: [], daily: [] });
    if (path === "/auth/oauth/providers") return send({ providers: [] });
    if (path === "/auth/me") return send(user);
    if (path === "/auth/login") {
      state.writes.push({ path, data: request.postDataJSON() });
      return send({ access_token: "fixture-only", refresh_token: "fixture-refresh", token_type: "bearer", user, session_id: "fixture-session", two_factor_required: false, challenge_token: null });
    }
    if (path === "/auth/fablespace/access") return send({ access_allowed: false, capabilities: [], access_level: null, expires_at: null, authorization_version: 0 });
    if (path === "/site/extensions" || path === "/tags") return send([]);
    if (path === "/drafts") {
      if (method === "DELETE") return send(true);
      if (method === "PUT") return send({ ...request.postDataJSON(), id: "fixture-draft", user_id: USER.id, version: 1, updated_at: NOW });
      return send([]);
    }
    if (path === "/drafts/lookup") return send(null);
    if (path === "/notifications") return send({ notifications: [], unread_count: 0 });
    if (path === "/notifications/stream") return route.fulfill({ status: 204, body: "" });
    if (path === "/boards") return send([BOARD]);
    if (path === "/boards/lounge") return send({ ...BOARD, latest_topics: [state.topic], child_boards: [] });
    if (path === "/boards/lounge/topics" && method === "POST") {
      const data = request.postDataJSON() as { title: string; raw_md: string };
      state.writes.push({ path, data });
      state.topic = { ...state.topic, title: data.title };
      state.posts = [post(1, data.raw_md)];
      return send(state.topic);
    }
    if (path === "/topics" || path === "/search" || path === "/boards/lounge/topics") return send([state.topic]);
    if (path === "/topics/201") return send(state.topic);
    if (path === "/topics/201/posts" && method === "POST") {
      const data = request.postDataJSON() as { raw_md: string };
      state.writes.push({ path, data });
      const reply = post(state.posts.length + 1, data.raw_md);
      state.posts.push(reply);
      return send(reply);
    }
    if (path === "/topics/201/posts") return send(state.posts);
    if (path === "/topics/201/notification-level") return send({ topic_id: "201", notification_level: "normal", last_read_post_number: 0 });
    if (path === "/users/id/101") return send({ ...user, is_persona: false, persona_kind: null, can_edit: true, topic_count: 1, post_count: 1, following_count: 0, follower_count: 0, badges: [] });
    if (path === "/users/forum_fixture/topics") return send([state.topic]);
    if (path === "/users/forum_fixture/activity") return send([]);
    state.unexpected.push(`${method} ${path}`);
    return route.fulfill({ status: 501, json: { error: { code: "unmocked_api", message: path } } });
  });
  return state;
}

