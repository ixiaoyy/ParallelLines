import { createRequire } from 'node:module';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

const require = createRequire('D:/work/ParallelLines/apps/web/package.json');
const { chromium } = require('@playwright/test');

const baseURL = 'http://127.0.0.1:5174';
const outDir = path.resolve('D:/work/ParallelLines/.tmp/design-review-20260528');
await mkdir(outDir, { recursive: true });

const now = new Date('2026-05-28T10:00:00+08:00');
const iso = (minusHours = 0) => new Date(now.getTime() - minusHours * 3600_000).toISOString();

const currentUser = {
  id: 'u1',
  username: '多动脑子z',
  email: '364437340@qq.com',
  avatar_url: '/uploads/mock-cat/content',
  display_name: '多动脑子z',
  bio: '更擅长把问题开成主题，适合作为讨论起点。',
  website_url: 'https://example.com',
  location: '平行线',
  role: 'admin',
  level: 5,
  trust_level: 4,
  trust_level_label: '核心成员',
  points_balance: 6010,
  experience_total: 2600,
  experience_to_next_level: 1200,
  level_progress_percent: 72,
  status: 'active',
  two_factor_enabled: false,
  profile_visibility: 'public',
  show_activity: true,
  interface_theme: 'system',
  locale: 'zh-CN',
  created_at: iso(24 * 2),
};

const boards = [
  board('b1', 'official', '官方动态', '平台公告、规则说明、活动通知与版本更新。', '#ca8a04', 18, 96, 320),
  board('b2', 'resources', '资源荟萃', '收集值得收藏的工具、资料、网站、课程和内容。', '#ea580c', 24, 142, 510),
  board('b3', 'welfare', '福利羊毛', '优惠信息、免费资源、限时活动、实用福利与避坑提醒。', '#ea580c', 9, 58, 240),
  board('b4', 'reading', '读书感悟', '分享读书摘记、阅读心得、金句摘录与文字感悟。', '#db2777', 11, 71, 360),
  board('b5', 'health', '健康百科', '交流饮食、运动、睡眠、心理与日常健康知识。', '#65a30d', 7, 31, 210),
  board('b6', 'frontier', '前沿快讯', '关注 AI、科技、行业变化和正在发生的新鲜事。', '#6366f1', 13, 84, 430),
  board('b7', 'lounge', '闲聊八卦', '轻松聊天、日常分享、兴趣交流、热点八卦和不那么严肃的话题。', '#475569', 15, 120, 620),
];

function board(id, slug, name, description, color, topic_count, post_count, follower_count) {
  return {
    id,
    slug,
    name,
    name_localizations: {},
    description,
    color,
    avatar_url: null,
    owner_id: 'u1',
    parent_board_id: null,
    parent_board_slug: null,
    parent_board_name: null,
    visibility: 'public',
    required_tags: [],
    allowed_tags: ['公告', '读书分享', '福利', '经验', '精华神帖', '发帖模板'],
    post_template: null,
    default_notification_level: 'normal',
    default_sort: 'latest',
    topic_count,
    post_count,
    follower_count,
    is_following: true,
    notification_level: 'tracking',
    can_create_topic: true,
    created_at: iso(24 * 80),
    updated_at: iso(2),
  };
}

function topic(id, slug, boardSlug, title, tags, opts = {}) {
  const b = boards.find((item) => item.slug === boardSlug) ?? boards[0];
  return {
    id,
    slug,
    title,
    title_localizations: {},
    board_id: b.id,
    board_slug: b.slug,
    board_name: b.name,
    board_color: b.color,
    author_id: opts.author_id ?? 'u1',
    author_name: opts.author_name ?? '多动脑子z',
    author_avatar_url: opts.author_avatar_url ?? '/uploads/mock-cat/content',
    author_role: opts.author_role ?? 'admin',
    author_level: opts.author_level ?? 5,
    author_trust_level: opts.author_trust_level ?? 4,
    author_trust_level_label: opts.author_trustLevelLabel ?? '核心成员',
    tags,
    accepted_answer_post_id: opts.solved ? 'p2' : null,
    solved_at: opts.solved ? iso(4) : null,
    solved_by_id: opts.solved ? 'u2' : null,
    answer_mode: false,
    vote_score: opts.vote_score ?? 8,
    vote_count: opts.vote_count ?? 12,
    my_vote: 0,
    poll: null,
    topic_type: opts.topic_type ?? 'regular',
    visibility: opts.visibility ?? 'public',
    status: opts.status ?? 'open',
    pinned: Boolean(opts.pinned),
    featured: Boolean(opts.featured),
    view_count: opts.view_count ?? 188,
    reply_count: opts.reply_count ?? 6,
    like_count: opts.like_count ?? 9,
    liked_by_me: false,
    bookmark_count: opts.bookmark_count ?? 3,
    bookmarked_by_me: false,
    hot_score: opts.hot_score ?? 48,
    last_posted_at: opts.last_posted_at ?? iso(1),
    created_at: opts.created_at ?? iso(12),
    updated_at: opts.updated_at ?? iso(1),
    merged_into_topic_id: null,
    share_url: `/topics/${id}/${slug}`,
    excerpt: opts.excerpt ?? `# ${title} 这个主题用于集中讨论，保留关键信息、补充背景和后续更新，方便后来者快速理解。`,
  };
}

const topics = [
  topic('t1', 'woman-star-reading', 'reading', '读《一个女人认为自己是行星》', ['读书分享'], { featured: true, reply_count: 0, view_count: 298, last_posted_at: iso(1 / 30), excerpt: '《一个女人认为自己是行星》收录了29位女性的故事，这里记录几个触动我的片段。' }),
  topic('t2', 'forum-first-record', 'official', '论坛初衷：记录、连接与共同成长', ['公告', '精华神帖'], { pinned: true, featured: true, reply_count: 0, view_count: 420, last_posted_at: iso(12), excerpt: '记录社区规则、发帖方向与共同维护方式，让每个人都能找到合适的位置。' }),
  topic('t3', 'community-rules', 'official', '社区规范：友善交流、尊重原创与保护隐私', ['发帖模板', '公告'], { pinned: true, reply_count: 0, view_count: 315, last_posted_at: iso(18), excerpt: '请勿发布隐私、侵权、攻击性内容；遇到问题可以举报或申诉。' }),
  topic('t4', 'idle-chat', 'lounge', '关于「闲聊八卦」', ['闲聊八卦'], { pinned: true, reply_count: 0, view_count: 96, last_posted_at: iso(24), excerpt: '轻松聊天、日常分享、兴趣交流、热点八卦和不那么严肃的话题。这个板块用于降低发帖压力。' }),
  topic('t5', 'mysql-task-refresh', 'resources', 'MySQL 8 下复现任务状态刷新卡住', ['经验', '排查'], { solved: true, reply_count: 7, view_count: 632, last_posted_at: iso(3), excerpt: '升级到 MySQL 8 后任务状态刷新偶发卡住，最后定位到通知游标字段缺失。' }),
  topic('t6', 'coupon-roundup', 'welfare', '本周可用工具与课程优惠合集', ['福利', '资源'], { reply_count: 3, view_count: 520, last_posted_at: iso(5), excerpt: '收集本周验证可用的工具、课程、云服务优惠，附简单避坑说明。' }),
];

const posts = [
  post('p1', 1, topics[0].title, '这本书里的故事都不长，但每段关系都很锋利。女性可以是自己的主宰，也可以重新定义自己的边界。'),
  post('p2', 2, '回复：关于阅读感受', '我觉得最好的地方是它没有把情绪解释得太满，留了很多空间给读者。', { author_name: '海盐', author_avatar_url: null, author_level: 3, author_role: 'user' }),
  post('p3', 3, '补充书单', '如果喜欢这个方向，可以接着读《厌女》《房思琪的初恋乐园》，但后者需要心理准备。', { author_name: '南风', author_avatar_url: null, author_level: 2, author_role: 'moderator' }),
];

function post(id, number, title, raw, opts = {}) {
  return {
    id,
    topic_id: 't1',
    user_id: opts.user_id ?? 'u1',
    author_name: opts.author_name ?? '多动脑子z',
    author_avatar_url: opts.author_avatar_url ?? '/uploads/mock-cat/content',
    author_role: opts.author_role ?? 'admin',
    author_level: opts.author_level ?? 5,
    author_trust_level: opts.author_trust_level ?? 4,
    author_trust_level_label: opts.author_trust_level_label ?? '核心成员',
    parent_id: null,
    post_number: number,
    raw_md: raw,
    cooked_html: `<p>${raw}</p>`,
    reply_count: 0,
    like_count: number === 1 ? 3 : 1,
    liked_by_me: false,
    accepted_answer: id === 'p2',
    vote_score: number === 1 ? 5 : 1,
    vote_count: number === 1 ? 6 : 2,
    my_vote: 0,
    share_url: `/topics/t1/woman-star-reading#post-${number}`,
    deleted_at: null,
    created_at: iso(12 - number),
    updated_at: iso(12 - number),
  };
}

const users = [
  { ...currentUser, topic_count: 8, post_count: 42, last_seen_at: iso(0.1), badges: [{ id: 'bd1', slug: 'core', name: '核心成员', description: '持续贡献', icon: '✓', points: 0, granted_at: iso(10) }] },
  { id: 'u2', username: '海盐', display_name: '海盐', avatar_url: null, role: 'moderator', level: 3, trust_level: 3, trust_level_label: '可信成员', points_balance: 820, topic_count: 4, post_count: 19, last_seen_at: iso(2), created_at: iso(24 * 30) },
  { id: 'u3', username: '南风', display_name: '南风', avatar_url: null, role: 'user', level: 2, trust_level: 2, trust_level_label: '活跃成员', points_balance: 360, topic_count: 2, post_count: 11, last_seen_at: iso(8), created_at: iso(24 * 16) },
];

function envelope(data, meta = undefined) {
  const payload = { data };
  if (meta) payload.meta = meta;
  return payload;
}

function json(route, data, status = 200, meta) {
  return route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(envelope(data, meta)) });
}

function noContentJson(route, data = {}) {
  return json(route, data);
}

function mockApi(route) {
  const request = route.request();
  const url = new URL(request.url());
  const path = url.pathname.replace(/^\/api\/v1/, '') || '/';
  const method = request.method();

  if (path.startsWith('/uploads/')) {
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#f59e0b"/><stop offset="1" stop-color="#60a5fa"/></linearGradient></defs><rect width="128" height="128" rx="32" fill="url(#g)"/><circle cx="46" cy="54" r="8" fill="#111827"/><circle cx="82" cy="54" r="8" fill="#111827"/><path d="M38 82c18 14 36 14 54 0" fill="none" stroke="#111827" stroke-width="8" stroke-linecap="round"/><path d="M34 18 20 44h28zM94 18 80 44h28z" fill="#fbbf24"/></svg>`;
    return route.fulfill({ status: 200, contentType: 'image/svg+xml', body: svg });
  }
  if (path === '/notifications/stream') {
    return route.fulfill({ status: 200, contentType: 'text/event-stream', body: '' });
  }
  if (path === '/auth/me') return json(route, currentUser);
  if (path === '/auth/sessions') return json(route, [
    { id: 's1', user_agent: 'Chrome / Windows', ip_address: '127.0.0.1', current: true, created_at: iso(48), last_seen_at: iso(0.1), revoked_at: null },
    { id: 's2', user_agent: 'Safari / iPad', ip_address: '192.168.1.8', current: false, created_at: iso(96), last_seen_at: iso(12), revoked_at: null },
  ]);
  if (path === '/auth/oauth/providers') return json(route, { providers: [] });
  if (path.startsWith('/auth/') && method !== 'GET') return noContentJson(route, { ok: true, updated_count: 1 });
  if (path === '/site/settings') return json(route, { settings: { site_title: '平行线', site_tagline: '让答案可追溯', brand_logo_url: '/logo-lines.png', brand_primary_color: '#409EFF' }, updated_at: iso(1) });
  if (path === '/site/extensions') return json(route, []);
  if (path === '/tags') return json(route, [{ id: 'tag1', name: '读书分享', slug: 'reading-share', topic_count: 12 }, { id: 'tag2', name: '公告', slug: 'announcement', topic_count: 8 }, { id: 'tag3', name: '福利', slug: 'welfare', topic_count: 10 }, { id: 'tag4', name: '经验', slug: 'experience', topic_count: 14 }, { id: 'tag5', name: '精华神帖', slug: 'featured', topic_count: 6 }]);
  if (path === '/drafts/lookup') return json(route, null);
  if (path === '/drafts') return json(route, { id: 'draft1', target_type: 'topic', target_id: null, draft_type: 'topic', data: {}, version: 1, updated_at: iso(0) });
  if (path === '/ai/similar-topics') return json(route, []);
  if (path === '/notifications') return json(route, { unread_count: 1, notifications: [
    { id: 'n1', type: 'board_new_topic', topic_id: 't1', post_id: null, actor_id: 'u2', actor_name: '海盐', data: { topic_title: topics[0].title, board_name: '读书感悟' }, read_at: null, created_at: iso(0.5) },
    { id: 'n2', type: 'liked', topic_id: 't5', post_id: null, actor_id: 'u3', actor_name: '南风', data: { topic_title: topics[4].title }, read_at: iso(2), created_at: iso(3) },
  ] });
  if (path === '/notifications/read') return noContentJson(route, { updated_count: 1, unread_count: 0 });

  if (path === '/boards') return json(route, boards);
  const boardTopics = path.match(/^\/boards\/([^/]+)\/topics/);
  if (boardTopics) {
    const slug = decodeURIComponent(boardTopics[1]);
    return json(route, topics.filter((t) => t.board_slug === slug || slug === 'welfare'));
  }
  const boardSettings = path.match(/^\/boards\/([^/]+)\/settings/);
  if (boardSettings) {
    const b = boards.find((item) => item.slug === decodeURIComponent(boardSettings[1])) ?? boards[0];
    return json(route, { board: b, members: [{ user_id: 'u1', username: '多动脑子z', role: 'owner', notification_level: 'tracking', joined_at: iso(48) }] });
  }
  const boardDetail = path.match(/^\/boards\/([^/]+)$/);
  if (boardDetail) {
    const b = boards.find((item) => item.slug === decodeURIComponent(boardDetail[1])) ?? boards[0];
    return json(route, { ...b, latest_topics: topics.filter((t) => t.board_slug === b.slug).slice(0, 3), child_boards: [] });
  }
  if (/^\/boards\/[^/]+\/follow$/.test(path)) return noContentJson(route, { active: true, follower_count: 241, notification_level: 'tracking' });

  if (path === '/topics') return json(route, topics, 200, { next_cursor: null });
  if (path === '/search') return json(route, topics.slice(0, 4), 200, { next_cursor: null });
  if (/^\/topics\/[^/]+\/posts/.test(path)) return json(route, posts);
  if (/^\/topics\/[^/]+\/notification-level/.test(path)) return json(route, { topic_id: 't1', notification_level: 'tracking' });
  if (/^\/topics\/[^/]+\/poll/.test(path)) return json(route, { id: 'poll1', topic_id: 't1', question: '你更关注哪类内容？', multiple_choice: false, closes_at: null, closed: false, total_votes: 12, selected_option_ids: [], options: [{ id: 'po1', label: '读书', position: 1, vote_count: 8 }, { id: 'po2', label: '经验', position: 2, vote_count: 4 }], created_at: iso(20), updated_at: iso(1) });
  if (/^\/topics\/[^/]+\/ai-summary/.test(path)) return json(route, { topic_id: 't1', summary: '讨论集中在阅读体验、女性处境和可延伸书单。', generated_at: iso(1) });
  const topicDetail = path.match(/^\/topics\/([^/]+)$/);
  if (topicDetail) return json(route, topics.find((t) => t.id === topicDetail[1]) ?? topics[0]);
  if (/^\/topics\/[^/]+\/(like|bookmark|vote|lifecycle|solution|move|split|merge)/.test(path)) return noContentJson(route, { active: true, count: 10, value: 1, score: 9 });
  if (/^\/posts\/[^/]+\/(vote|revisions)/.test(path)) {
    if (path.endsWith('/revisions')) return json(route, []);
    return noContentJson(route, { value: 1, score: 6, count: 8 });
  }
  if (/^\/posts\//.test(path)) return json(route, posts[0]);

  if (path === '/users/directory') return json(route, users);
  if (path === '/users/me') return json(route, { ...currentUser, can_edit: true, topic_count: 8, post_count: 42, badges: users[0].badges });
  if (path === '/users/me/profile') return json(route, { ...currentUser, can_edit: true, topic_count: 8, post_count: 42, badges: users[0].badges });
  if (path === '/users/messages') return json(route, [{ topic: { ...topics[0], topic_type: 'private_message', visibility: 'private_message', title: '整理测试文档的内部沟通' }, participants: [{ user_id: 'u1', username: '多动脑子z', role: 'owner', last_read_post_number: 1, muted: false }, { user_id: 'u2', username: '海盐', role: 'participant', last_read_post_number: 1, muted: false }], unread: true }]);
  const userActivity = path.match(/^\/users\/([^/]+)\/activity/);
  if (userActivity) return json(route, [{ id: 'a1', type: 'post', created_at: iso(1), topic_id: 't1', topic_title: topics[0].title, topic_slug: topics[0].slug, post_number: 1, excerpt: '分享了一段新的阅读感受。' }]);
  const userTopics = path.match(/^\/users\/([^/]+)\/topics/);
  if (userTopics) return json(route, topics.slice(0, 3));
  const rel = path.match(/^\/users\/([^/]+)\/relationship/);
  if (rel) return json(route, { target_user_id: 'u1', target_username: decodeURIComponent(rel[1]), following: false, ignored: false, blocked: false, followed_by: false });
  const userProfile = path.match(/^\/users\/([^/]+)$/);
  if (userProfile) return json(route, { ...currentUser, can_edit: true, topic_count: 8, post_count: 42, badges: users[0].badges });

  if (path === '/email/preferences') return json(route, { user_id: 'u1', email: currentUser.email, digest_frequency: 'daily', muted_until: null, preferences: { replies: true, mentions: true, digest: true, marketing: false }, created_at: iso(100), updated_at: iso(1) });
  if (path === '/events') return json(route, [{ id: 'e1', title: '周末读书分享会', description: '轻量分享最近读到的一本书。', location: '线上', timezone: 'Asia/Shanghai', start_at: iso(-24), end_at: iso(-25), capacity: 30, attendee_count: 12, my_rsvp: 'going', created_by_id: 'u1', created_by_name: '多动脑子z', created_at: iso(48), updated_at: iso(2) }]);
  if (/^\/events\//.test(path)) return noContentJson(route, { event_id: 'e1', status: 'going', attendee_count: 13 });

  const reviewable = { id: 'r1', type: 'queued_topic', status: 'pending', priority: 60, source: 'content_policy', source_summary: '新主题包含需要复核的敏感词', target_type: 'topic', target_id: 't1', board_id: 'b4', board_name: '读书感悟', topic_id: 't1', post_id: null, flag_id: null, created_by_id: 'u1', created_by_name: '多动脑子z', target_user_id: null, target_user_name: null, assigned_to_id: null, assigned_to_name: null, assigned_at: null, resolved_by_id: null, resolved_by_name: null, resolved_at: null, appeal_available: true, data: { title: topics[0].title, excerpt: topics[0].excerpt }, events: [], created_at: iso(6), updated_at: iso(6) };
  if (path === '/moderation/reviewables' || path === '/moderation/reviewables/me') return json(route, [reviewable]);
  if (path === '/moderation/queue') return json(route, []);
  if (path === '/moderation/audit-logs') return json(route, [{ id: 'log1', actor_id: 'u1', actor_name: '多动脑子z', action: 'topic_created', target_type: 'topic', target_id: 't1', board_id: 'b4', data: {}, created_at: iso(1) }]);
  if (/^\/moderation\//.test(path)) return noContentJson(route, { ok: true });

  if (path === '/admin/system') return json(route, { version: 'local', environment: 'local', services: [{ name: 'api', status: 'ok', detail: 'Mocked by Playwright' }, { name: 'queue', status: 'ok', detail: 'Idle' }], stats: { users: 128, boards: 7, topics: 86, posts: 420, pending_flags: 1, audit_logs: 18, spam_actions: 2 }, queue: { queued: 0, running: 0, dead: 0, worker: 'mock', poll_seconds: 5, batch_size: 25, retry_delay_seconds: 60, hot_rank_interval_seconds: 300, upload_cleanup_interval_seconds: 3600, session_cleanup_interval_seconds: 3600 }, recent_audit_logs: [{ id: 'log1', actor_id: 'u1', actor_name: '多动脑子z', action: 'settings.updated', target_type: 'setting', target_id: 'brand', board_id: null, data: {}, created_at: iso(2) }], recent_email_logs: [{ to_email: currentUser.email, subject: '验证邮件', kind: 'verification', sent_at: iso(3) }], recent_errors: [] });
  if (path === '/admin/settings') return json(route, []);
  if (path === '/admin/users') return json(route, users.map((u) => ({ ...currentUser, ...u, email: `${u.username}@example.com`, status: 'active', two_factor_enabled: false, experience_total: 1200, experience_to_next_level: 600, level_progress_percent: 52, updated_at: iso(1), badges: [] })));
  if (path === '/admin/badges') return json(route, users[0].badges);
  if (path === '/admin/api-keys') return json(route, [{ id: 'key1', name: 'Docs Bot', token_prefix: 'pl_live', scopes: ['read'], key_type: 'personal', owner_user_id: 'u1', created_by_id: 'u1', last_used_at: iso(4), expires_at: null, disabled_at: null, note: null, created_at: iso(200), updated_at: iso(4) }]);
  if (path === '/admin/webhooks') return json(route, []);
  if (path === '/admin/webhook-deliveries') return json(route, []);
  if (path === '/admin/audit-logs') return json(route, [{ id: 'log1', actor_id: 'u1', actor_name: '多动脑子z', action: 'mock.review', target_type: 'topic', target_id: 't1', board_id: 'b4', data: {}, created_at: iso(1) }]);
  if (path.startsWith('/admin/')) return json(route, []);

  return json(route, method === 'GET' ? {} : { ok: true });
}

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 });
await context.addInitScript(() => {
  localStorage.setItem('parallellines.access_token', 'mock-access-token');
  localStorage.setItem('parallellines.refresh_token', 'mock-refresh-token');
});
await context.route('**/api/v1/**', mockApi);
const page = await context.newPage();
page.on('console', (msg) => {
  if (msg.type() === 'error') console.log('[browser console]', msg.text());
});
page.on('pageerror', (error) => console.log('[page error]', error.message));

const pages = [
  ['01-home', '/', '首页'],
  ['02-boards', '/boards', '版块目录'],
  ['03-board-welfare', '/b/welfare', '版块详情：福利羊毛'],
  ['04-topic-detail', '/topics/t1/woman-star-reading', '主题详情'],
  ['05-new-topic', '/new-topic', '发帖页'],
  ['06-profile', '/u/%E5%A4%9A%E5%8A%A8%E8%84%91%E5%AD%90z', '个人中心'],
  ['07-security', '/security', '安全中心'],
  ['08-email', '/email-preferences', '邮件偏好'],
  ['09-messages', '/messages', '私信'],
  ['10-events', '/events', '活动'],
  ['11-reviewables', '/moderation/reviewables', '我的申诉/审核'],
  ['12-admin', '/admin', '后台'],
  ['13-admin-moderation', '/admin/moderation', '后台审核'],
  ['14-search', '/search?q=MySQL', '搜索页'],
];

const results = [];
for (const [name, urlPath, label] of pages) {
  await page.goto(baseURL + urlPath, { waitUntil: 'networkidle', timeout: 20000 });
  await page.waitForTimeout(700);

  if (name === '03-board-welfare') {
    const hot = page.getByText('热门', { exact: true }).first();
    if (await hot.count()) await hot.click().catch(() => {});
  }
  if (name === '04-topic-detail') {
    const more = page.getByLabel('更多楼层操作').first();
    if (await more.count()) {
      await more.click().catch(() => {});
      await page.mouse.click(30, 300).catch(() => {});
    }
  }
  if (name === '05-new-topic') {
    const title = page.getByPlaceholder(/标题|粘贴链接/).first();
    if (await title.count()) await title.fill('整理一次设计评审反馈').catch(() => {});
  }
  const file = path.join(outDir, `${name}.png`);
  await page.screenshot({ path: file, fullPage: true });
  const bodyText = await page.locator('body').innerText().catch(() => '');
  results.push({ name, label, path: file, url: baseURL + urlPath, text: bodyText.slice(0, 500) });
}

const cardHtml = `<!doctype html><meta charset="utf-8"><style>
body{margin:0;padding:24px;background:#f3f7fb;font-family:system-ui,'Microsoft YaHei',sans-serif;color:#243044}.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:18px}.card{background:white;border:1px solid #dbe7f3;border-radius:18px;padding:12px;box-shadow:0 12px 28px rgba(22,35,56,.08)}h1{font-size:26px;margin:0 0 18px}.title{font-weight:800;margin:0 0 8px}.card img{width:100%;height:360px;object-fit:cover;object-position:top;border-radius:12px;border:1px solid #e5edf5}</style><h1>平行线页面设计巡检截图</h1><div class="grid">${results.map((r) => `<div class="card"><div class="title">${r.name} · ${r.label}</div><img src="file:///${r.path.replaceAll('\\', '/')}"></div>`).join('')}</div>`;
const contactHtml = path.join(outDir, 'contact-sheet.html');
await writeFile(contactHtml, cardHtml, 'utf8');
const contact = await context.newPage();
await contact.goto('file:///' + contactHtml.replaceAll('\\', '/'));
await contact.setViewportSize({ width: 1600, height: 2600 });
await contact.screenshot({ path: path.join(outDir, '00-contact-sheet.png'), fullPage: true });
await writeFile(path.join(outDir, 'results.json'), JSON.stringify(results, null, 2), 'utf8');
await browser.close();
console.log(JSON.stringify({ outDir, contactSheet: path.join(outDir, '00-contact-sheet.png'), pages: results.map((r) => ({ name: r.name, label: r.label, path: r.path })) }, null, 2));

