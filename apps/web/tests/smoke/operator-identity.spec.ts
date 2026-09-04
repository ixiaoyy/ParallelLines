import { expect, test, type Page } from "@playwright/test";

import type { PersonaKind } from "../../src/entities/user/model";
import type { AdminUserResponse } from "../../src/features/admin/model";
import type { BoardResponse } from "../../src/features/boards/model";
import type { PostResponse } from "../../src/features/posts/model";
import type { TopicResponse } from "../../src/features/topics/model";
import type { UserProfile } from "../../src/features/users/model";
import {
  isPersonaKind,
  normalizePersonaFlag,
  operatorIdentity,
  OPERATOR_IDENTITIES,
} from "../../src/features/users/operatorIdentity";
import {
  buildForumTopicStructuredData,
  buildProfileStructuredData,
} from "../../src/shared/seo/structuredData";

test.use({ serviceWorkers: "block" });

type FixtureUser = UserProfile & AdminUserResponse;
interface FixtureState {
  users: FixtureUser[];
  topics: TopicResponse[];
  writes: Record<string, unknown>[];
  unexpected: string[];
  errors: string[];
  omitKinds: boolean;
  missingIdentity: boolean;
}

const NOW = new Date().toISOString();
const LOCAL_ORIGIN = new URL(
  process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5173",
).origin;

/** Builds one explicit, test-only user; no registration or account API is called. */
function makeUser(id: string, kind: PersonaKind | null, managed = true): FixtureUser {
  return {
    id,
    username: `界面测试账号${id}`,
    email: `fixture${id}@example.com`,
    display_name: null,
    bio: "这是用于界面验证的固定资料，不是真实社区账号。",
    website_url: null,
    location: null,
    avatar_url: null,
    role: "user",
    status: "active",
    is_persona: managed,
    persona_kind: kind,
    level: 0,
    trust_level: 1,
    trust_level_label: "基础成员",
    points_balance: 10,
    experience_total: 0,
    experience_to_next_level: 100,
    level_progress_percent: 0,
    two_factor_enabled: false,
    profile_visibility: "public",
    show_activity: true,
    can_edit: false,
    topic_count: 1,
    post_count: 2,
    following_count: 2,
    follower_count: 0,
    badges: [],
    created_at: NOW,
    updated_at: NOW,
    last_seen_at: NOW,
  };
}

/** Returns a complete public topic transport fixture using the supplied author. */
function makeTopic(id: string, author: FixtureUser): TopicResponse {
  return {
    id,
    slug: `topic-${id}`,
    title: `公开身份验证主题 ${id}`,
    board_id: "10",
    board_slug: "lounge",
    board_name: "闲聊",
    board_color: "#409EFF",
    board_visibility: "public",
    author_id: author.id,
    author_name: author.username,
    author_avatar_url: null,
    author_role: author.role,
    author_is_persona: author.is_persona,
    author_persona_kind: author.persona_kind,
    author_level: 0,
    author_trust_level: 1,
    author_trust_level_label: "基础成员",
    tags: id === "201" ? ["今日节目"] : [],
    accepted_answer_post_id: null,
    solved_at: null,
    solved_by_id: null,
    answer_mode: false,
    vote_score: 0,
    vote_count: 0,
    my_vote: 0,
    poll: null,
    topic_type: "regular",
    visibility: "public",
    status: "open",
    pinned: false,
    featured: false,
    view_count: 10,
    reply_count: 2,
    like_count: 0,
    hot_score: 1,
    last_posted_at: NOW,
    created_at: NOW,
    updated_at: NOW,
    merged_into_topic_id: null,
    share_url: `/topics/${id}/topic-${id}`,
    excerpt: "固定测试内容，用于检查作者身份在不同页面中的一致性。",
  };
}

/** Returns a source-preserving post fixture with explicit author identity and counters. */
function makePost(topic: TopicResponse, author: FixtureUser, floor: number): PostResponse {
  return {
    id: `${topic.id}${floor}`,
    topic_id: topic.id,
    user_id: author.id,
    author_name: author.username,
    author_avatar_url: null,
    author_role: author.role,
    author_is_persona: author.is_persona,
    author_persona_kind: author.persona_kind,
    author_level: 0,
    author_trust_level: 1,
    author_trust_level_label: "基础成员",
    parent_id: null,
    post_number: floor,
    raw_md: "用于验证身份标识的固定正文，原文不应改写。",
    cooked_html: "<p>用于验证身份标识的固定正文，原文不应改写。</p>",
    reply_count: 0,
    like_count: 0,
    accepted_answer: false,
    vote_score: 0,
    vote_count: 0,
    my_vote: 0,
    share_url: `${topic.share_url}#post-${floor}`,
    deleted_at: null,
    created_at: NOW,
    updated_at: NOW,
  };
}

/** Installs complete API interception and a test-only auth state; external requests are blocked. */
async function installFixture(page: Page, admin = false): Promise<FixtureState> {
  const users = [
    makeUser("101", "editorial"),
    makeUser("102", "automation"),
    makeUser("103", "fictional"),
    makeUser("104", null, false),
    makeUser("105", null),
  ];
  users[2].display_name = "这是一位用于检查窄屏长昵称与创作角色标识换行的测试作者";
  const state: FixtureState = {
    users,
    topics: users.map((user, index) => makeTopic(String(201 + index), user)),
    writes: [],
    unexpected: [],
    errors: [],
    omitKinds: false,
    missingIdentity: false,
  };
  const currentAdmin = { ...makeUser("999", null, false), role: "admin" };
  const board: BoardResponse = {
    id: "10",
    slug: "lounge",
    name: "闲聊",
    description: "用于前端验证的固定版块。",
    color: "#409EFF",
    avatar_url: null,
    owner_id: null,
    parent_board_id: null,
    parent_board_slug: null,
    parent_board_name: null,
    visibility: "public",
    required_tags: [],
    allowed_tags: [],
    post_template: null,
    default_notification_level: "normal",
    default_sort: "latest",
    topic_count: 5,
    post_count: 15,
    follower_count: 0,
    is_following: false,
    notification_level: null,
    can_create_topic: true,
    created_at: NOW,
    updated_at: NOW,
  };
  await page.addInitScript((asAdmin) => {
    if (asAdmin) {
      localStorage.setItem("parallellines.access_token", "test-only-not-a-real-token");
    }
  }, admin);
  page.on("pageerror", (error) => state.errors.push(error.message));

  // Undefined values are omitted only on the wire to simulate historical API payloads.
  const wireUser = (user: FixtureUser) => ({
    ...user,
    is_persona: state.missingIdentity ? undefined : user.is_persona,
    persona_kind: state.missingIdentity || state.omitKinds ? undefined : user.persona_kind,
  });
  const wireTopic = (topic: TopicResponse) => {
    const author = users.find((user) => user.id === topic.author_id)!;
    return {
      ...topic,
      author_is_persona: state.missingIdentity ? undefined : author.is_persona,
      author_persona_kind: state.missingIdentity || state.omitKinds ? undefined : author.persona_kind,
    };
  };
  const wirePost = (post: PostResponse) => ({
    ...post,
    author_is_persona: state.missingIdentity ? undefined : post.author_is_persona,
    author_persona_kind: state.missingIdentity || state.omitKinds ? undefined : post.author_persona_kind,
  });

  await page.route("**/*", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (!url.pathname.startsWith("/api/")) {
      if (url.origin === LOCAL_ORIGIN) {
        await route.continue();
      } else {
        state.unexpected.push(`External request: ${url.origin}${url.pathname}`);
        await route.abort();
      }
      return;
    }
    const path = decodeURIComponent(url.pathname.replace(/^\/api\/v1/, ""));
    const send = (data: unknown) => route.fulfill({ json: { data } });
    if (path === "/site/settings") {
      await send({ settings: { site_title: "平行线", site_tagline: "前端固定数据验证", brand_primary_color: "#409EFF" }, updated_at: null });
    } else if (path === "/site/extensions" || path === "/admin/badges") {
      await send([]);
    } else if (path === "/site/visits" && request.method() === "POST") {
      await send({ recorded: false });
    } else if (path === "/auth/me") {
      await send({ ...currentAdmin, locale: "zh-CN", interface_theme: "system" });
    } else if (path === "/auth/fablespace/access") {
      await send({ access_allowed: false, capabilities: [], access_level: null, expires_at: null, authorization_version: 0 });
    } else if (path === "/notifications") {
      await send({ notifications: [], unread_count: 0 });
    } else if (path === "/notifications/stream") {
      await route.fulfill({ status: 204, body: "" });
    } else if (path === "/boards") {
      await send([board]);
    } else if (path === "/tags") {
      await send([{ id: "1", name: "今日节目", slug: "program", topic_count: 1 }]);
    } else if (path === "/boards/lounge") {
      await send({ ...board, latest_topics: state.topics.map(wireTopic), child_boards: [] });
    } else if (path === "/topics" || path === "/search" || path === "/boards/lounge/topics") {
      await send(state.topics.map(wireTopic));
    } else if (/^\/topics\/\d+$/.test(path)) {
      await send(wireTopic(state.topics.find((topic) => topic.id === path.split("/")[2])!));
    } else if (/^\/topics\/\d+\/posts$/.test(path)) {
      const topic = state.topics.find((item) => item.id === path.split("/")[2])!;
      const author = users.find((user) => user.id === topic.author_id)!;
      await send([
        makePost(topic, author, 1),
        makePost(topic, users[1], 2),
        makePost(topic, users[3], 3),
      ].map(wirePost));
    } else if (path === "/users/directory" || path === "/admin/users") {
      await send(users.map(wireUser));
    } else if (/^\/users\/id\/\d+$/.test(path)) {
      await send(wireUser(users.find((user) => user.id === path.split("/")[3])!));
    } else if (/^\/users\/[^/]+\/topics$/.test(path)) {
      await send(state.topics.filter((topic) => topic.author_name === path.split("/")[2]).map(wireTopic));
    } else if (/^\/users\/[^/]+\/relationships\/(following|followers)$/.test(path)) {
      await send([users[1], users[2]].map((user) => ({ ...wireUser(user), followed_at: NOW })));
    } else if (/^\/users\/[^/]+\/activity$/.test(path)) {
      await send([]);
    } else if (/^\/users\/[^/]+\/relationship$/.test(path)) {
      await send({ target_user_id: "101", target_username: users[0].username, following: false, ignored: false, blocked: false, followed_by: false });
    } else if (/^\/users\/[^/]+$/.test(path)) {
      await send(wireUser(users.find((user) => user.username === path.split("/")[2])!));
    } else if (/^\/admin\/users\/\d+$/.test(path) && request.method() === "PUT") {
      const body: unknown = request.postDataJSON();
      if (typeof body !== "object" || body === null || Array.isArray(body)) {
        throw new Error("Expected an admin update object");
      }
      const values = body as Record<string, unknown>;
      state.writes.push(values);
      const target = users.find((user) => user.id === path.split("/")[3])!;
      if (typeof values.is_persona === "boolean") target.is_persona = values.is_persona;
      if (values.persona_kind === null || isPersonaKind(values.persona_kind)) {
        target.persona_kind = target.is_persona ? values.persona_kind : null;
      }
      await send(wireUser(target));
    } else {
      state.unexpected.push(`${request.method()} ${path}`);
      await route.fulfill({ status: 501, json: { error: { code: "unmocked_api", message: path } } });
    }
  });
  return state;
}

/** Verifies viewport overflow and actual small-label contrast without changing the page. */
async function expectNoOverflow(page: Page): Promise<void> {
  const sizes = await page.evaluate(() => ({
    page: document.documentElement.scrollWidth,
    viewport: window.innerWidth,
  }));
  expect(sizes.page).toBeLessThanOrEqual(sizes.viewport + 1);
  const contrasts = await page.locator(".operator-identity").evaluateAll((badges) =>
    badges.filter((badge) => badge.getBoundingClientRect().width > 0).map((badge) => {
      const style = getComputedStyle(badge);
      const luminance = (color: string) => {
        const channels = (color.match(/[\d.]+/g) ?? []).slice(0, 3).map(Number).map((value) => {
          const unit = value / 255;
          return unit <= 0.04045 ? unit / 12.92 : ((unit + 0.055) / 1.055) ** 2.4;
        });
        return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
      };
      const foreground = luminance(style.color);
      const background = luminance(style.backgroundColor);
      return (Math.max(foreground, background) + 0.05) / (Math.min(foreground, background) + 0.05);
    }),
  );
  for (const contrast of contrasts) expect(contrast).toBeGreaterThanOrEqual(4.5);
}

/** Checks the fixture exhausted every API and no Vue runtime error occurred. */
function expectIsolated(state: FixtureState): void {
  expect(state.unexpected).toEqual([]);
  expect(state.errors).toEqual([]);
}

test("identity catalogue and SEO builders respect explicit ownership", () => {
  expect(Object.values(OPERATOR_IDENTITIES).map((identity) => identity.label)).toEqual([
    "官方栏目", "自动账号", "创作角色",
  ]);
  expect(OPERATOR_IDENTITIES.editorial.description).toBe("该账号由平行线运营维护，用于栏目内容发布。");
  expect(OPERATOR_IDENTITIES.automation.description).toBe("该账号由平行线运营维护，用于自动化发布或辅助互动。");
  expect(OPERATOR_IDENTITIES.fictional.description).toBe("该账号是平行线运营的创作角色，不代表独立社区成员。");
  expect(operatorIdentity(true, "future-kind")?.label).toBe("运营角色");
  expect(operatorIdentity(false, "editorial")).toBeNull();
  expect(operatorIdentity(undefined, "editorial")).toBeNull();
  expect(normalizePersonaFlag(undefined)).toBeNull();
  const input = {
    topicUrl: "https://example.com/topics/1/example",
    title: "fixture",
    boardName: "fixture",
    boardUrl: "https://example.com/b/lounge",
    publishedAt: NOW,
    topicAuthorIsPersona: false,
    authorIsPersona: false,
    authorName: "member",
    text: "original",
    replyCount: 2,
    viewCount: 0,
    likeCount: 0,
    replies: [
      { authorIsPersona: true, authorName: "operator", publishedAt: NOW, postNumber: 2, text: "retained on page" },
      { authorIsPersona: false, authorName: "member2", publishedAt: NOW, postNumber: 3, text: "reply" },
    ],
  };
  const result = buildForumTopicStructuredData(input);
  expect(result?.commentCount).toBe(2);
  expect(result?.comment).toHaveLength(1);
  expect(buildForumTopicStructuredData({ ...input, topicAuthorIsPersona: true })).toBeNull();
  expect(buildForumTopicStructuredData({ ...input, authorIsPersona: null })).toBeNull();
  expect(buildProfileStructuredData({
    isPersona: true, profileUrl: "https://example.com/members/1", username: "operator",
    displayName: "operator", bio: null, avatarUrl: null, createdAt: NOW, topicCount: 1, postCount: 2,
  })).toBeNull();
});

test("home, board and search lists expose the same subtype labels", async ({ page }) => {
  const state = await installFixture(page);
  await page.goto("/");
  await expect(page.locator(".home-topic-row")).toHaveCount(5);
  for (const kind of ["editorial", "automation", "fictional", "managed"]) {
    await expect(page.locator(`.home-topic-row [data-persona-kind="${kind}"]`)).toHaveCount(1);
  }
  await expect(page.locator(".daily-program [data-persona-kind=editorial]")).toBeVisible();
  await page.goto("/b/lounge");
  await expect(page.locator(".topic-row [data-persona-kind]")).toHaveCount(4);
  await page.goto("/search?q=身份");
  await expect(page.locator(".topic-row [data-persona-kind]")).toHaveCount(4);
  expectIsolated(state);
});

test("topic main authors, replies and SPA SEO survive narrow screens", async ({ page }, testInfo) => {
  const state = await installFixture(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/topics/201/topic-201");
  await expect(page.locator(".topic-detail-hero [data-persona-kind=editorial]")).toBeVisible();
  await expect(page.locator("#post-1 .post-header")).toHaveCount(0);
  await expect(page.locator("#post-2 [data-persona-kind=automation]")).toBeVisible();
  await expect(page.locator("#post-3 .operator-identity")).toHaveCount(0);
  await expect(page.locator("#seo-page-structured-data")).toHaveCount(0);
  await expectNoOverflow(page);
  await page.screenshot({ path: testInfo.outputPath("topic-390.png"), fullPage: true });
  await page.setViewportSize({ width: 320, height: 780 });
  await expectNoOverflow(page);
  await expect(page.locator(".topic-detail-hero .operator-identity")).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("topic-320.png"), fullPage: true });
  const timeOrigin = await page.evaluate(() => performance.timeOrigin);
  for (const id of ["202", "203", "204"]) {
    await page.getByRole("button", { name: /下一篇/ }).click();
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(`公开身份验证主题 ${id}`);
  }
  expect(await page.evaluate(() => performance.timeOrigin)).toBe(timeOrigin);
  await expect(page.locator("#seo-page-structured-data")).toHaveCount(1);
  const schema = JSON.parse(await page.locator("#seo-page-structured-data").textContent() ?? "{}");
  expect(schema["@type"]).toBe("DiscussionForumPosting");
  expect(schema.commentCount).toBe(2);
  expect(schema.comment).toHaveLength(1);
  expect(schema.comment[0].author.name).toBe(state.users[3].username);
  await page.getByRole("button", { name: /下一篇/ }).click();
  await expect(page.locator(".topic-detail-hero [data-persona-kind=managed]")).toBeVisible();
  await expect(page.locator("#seo-page-structured-data")).toHaveCount(0);
  expectIsolated(state);
});

test("profile variants, relationship cards and directory retain disclosure", async ({ page }, testInfo) => {
  const state = await installFixture(page);
  await page.goto("/members/101");
  await expect(page.locator(".profile-kicker [data-persona-kind=editorial]")).toBeVisible();
  await expect(page.locator(".profile-operator-notice")).toHaveText(OPERATOR_IDENTITIES.editorial.description);
  await expect(page.locator(".topic-row--profile [data-persona-kind=editorial]")).toHaveCount(1);
  await expect(page.locator("#seo-page-structured-data")).toHaveCount(0);
  await page.locator(".profile-section-switcher button").filter({ hasText: "关注" }).click();
  await expect(page.locator(".profile-social-user [data-persona-kind]")).toHaveCount(2);
  await page.setViewportSize({ width: 320, height: 780 });
  await page.goto("/users");
  await expect(page.locator(".directory-card [data-persona-kind]")).toHaveCount(4);
  await expectNoOverflow(page);
  await page.screenshot({ path: testInfo.outputPath("directory-320.png"), fullPage: true });
  await page.goto("/members/104");
  await expect(page.locator(".profile-kicker .operator-identity")).toHaveCount(0);
  await expect(page.locator("#seo-page-structured-data")).toHaveCount(1);
  expectIsolated(state);
});

test("admin can classify, clear a subtype, and close operator ownership", async ({ page }, testInfo) => {
  const state = await installFixture(page, true);
  await page.setViewportSize({ width: 1366, height: 900 });
  await page.goto("/admin/users");
  const kind = page.getByRole("combobox", { name: /公开身份/ });
  await expect(kind).toHaveValue("editorial");
  await kind.selectOption("automation");
  await page.getByRole("button", { name: "保存用户变更" }).click();
  await expect.poll(() => state.writes.length).toBe(1);
  expect(state.writes[0]).toMatchObject({ is_persona: true, persona_kind: "automation", role: "user" });
  await expect(page.locator(".user-detail-header [data-persona-kind=automation]")).toBeVisible();
  await expectNoOverflow(page);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: testInfo.outputPath("admin-identity.png"), fullPage: true });
  await kind.selectOption({ label: "未细分（运营角色）" });
  await page.getByRole("button", { name: "保存用户变更" }).click();
  await expect.poll(() => state.writes.length).toBe(2);
  expect(state.writes[1]).toMatchObject({ is_persona: true, persona_kind: null });
  await kind.selectOption("fictional");
  await page.locator(".user-detail-pane").getByRole("combobox", { name: /账号归类/ }).selectOption({ label: "普通账号" });
  await expect(kind).toBeDisabled();
  await page.getByRole("button", { name: "保存用户变更" }).click();
  await expect.poll(() => state.writes.length).toBe(3);
  expect(state.writes[2]).toMatchObject({ is_persona: false, persona_kind: null });
  await expect(page.locator(".user-detail-header .operator-identity")).toHaveCount(0);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator(".user-list button").first().click();
  await expect(kind).toBeVisible();
  await expect(kind).toBeDisabled();
  await expectNoOverflow(page);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: testInfo.outputPath("admin-390.png"), fullPage: true });
  expectIsolated(state);
});

test("old payloads keep managed fallback and obsolete caches are not trusted", async ({ page }) => {
  const state = await installFixture(page);
  state.omitKinds = true;
  await page.goto("/");
  await expect(page.locator(".home-topic-row [data-persona-kind=managed]")).toHaveCount(4);
  state.missingIdentity = true;
  await page.goto("/topics/201/topic-201");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("公开身份验证主题 201");
  await expect(page.locator(".topic-detail-hero .operator-identity")).toHaveCount(0);
  await expect(page.locator("#seo-page-structured-data")).toHaveCount(0);
  await page.goto("/users");
  const caches = await page.evaluate(async (moduleUrl) => {
    const cache = await import(moduleUrl);
    const old = {
      id: "900", slug: "old", title: "旧缓存", boardSlug: "lounge", boardName: "闲聊",
      authorName: "旧作者", tags: [], excerpt: "old", replyCount: 0, viewCount: 0,
      lastPostedAt: new Date().toISOString(),
    };
    const oldKey = "parallellines.homeFeed.topics.v1:anonymous:latest";
    const newKey = "parallellines.homeFeed.topics.v2:anonymous:latest";
    localStorage.removeItem(newKey);
    localStorage.setItem("persona-test-unrelated", "preserve");
    localStorage.setItem(oldKey, JSON.stringify({ value: [old], updatedAt: Date.now() }));
    const oldVersion = cache.readCachedHomeFeedTopics("latest");
    localStorage.setItem(newKey, JSON.stringify({ value: [old], updatedAt: Date.now() }));
    const missingFields = cache.readCachedHomeFeedTopics("latest");
    const complete = { ...old, authorIsPersona: true, authorPersonaKind: null };
    localStorage.setItem(newKey, JSON.stringify({ value: [complete], updatedAt: Date.now() }));
    const managed = cache.readCachedHomeFeedTopics("latest");
    const saved = localStorage.getItem(newKey);
    cache.cacheHomeFeedTopics("latest", [{ ...complete, authorIsPersona: null }]);
    return {
      oldVersion, missingFields, managed,
      preserved: localStorage.getItem(newKey) === saved,
      unrelated: localStorage.getItem("persona-test-unrelated"),
    };
  }, "/src/pages/home/homeRailCache.ts");
  expect(caches.oldVersion).toEqual([]);
  expect(caches.missingFields).toEqual([]);
  expect(caches.managed).toHaveLength(1);
  expect(caches.preserved).toBe(true);
  expect(caches.unrelated).toBe("preserve");
  expectIsolated(state);
});
