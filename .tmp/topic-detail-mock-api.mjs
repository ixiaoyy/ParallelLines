import http from 'node:http';

const now = '2026-06-03T10:00:00+08:00';
const topic = {
  id: 'health-wiki-intro',
  slug: 'about-health-wiki',
  title: '关于「健康百科」',
  board_id: 'board-health',
  board_slug: 'health',
  board_name: '健康百科',
  board_color: '#65a30d',
  author_id: 'u_brain',
  author_name: '多动脑子z',
  author_avatar_url: null,
  author_role: 'admin',
  author_level: 8,
  author_trust_level: 4,
  author_trust_level_label: '管理员',
  tags: ['健康百科'],
  accepted_answer_post_id: null,
  solved_at: null,
  solved_by_id: null,
  answer_mode: false,
  vote_score: 12,
  vote_count: 12,
  my_vote: 0,
  poll: null,
  topic_type: 'regular',
  visibility: 'public',
  status: 'open',
  pinned: true,
  featured: false,
  view_count: 135,
  reply_count: 1,
  like_count: 12,
  liked_by_me: false,
  bookmark_count: 8,
  bookmarked_by_me: false,
  hot_score: 15.35,
  last_posted_at: '2026-06-02T18:00:00+08:00',
  created_at: '2026-05-26T09:00:00+08:00',
  updated_at: '2026-06-02T18:00:00+08:00',
  merged_into_topic_id: null,
  share_url: 'http://127.0.0.1:5174/topics/health-wiki-intro/about-health-wiki',
  excerpt: '交流饮食、运动、睡眠、心理与日常健康知识。这个板块用于分享日常健康知识和个人实践经验，涉及疾病、用药和诊断时，应提醒大家以专业医生意见为准。',
};

const posts = [
  {
    id: 'post-1',
    topic_id: topic.id,
    user_id: 'u_brain',
    author_name: '多动脑子z',
    author_avatar_url: null,
    author_role: 'admin',
    author_level: 8,
    author_trust_level: 4,
    author_trust_level_label: '管理员',
    parent_id: null,
    post_number: 1,
    raw_md: '关于「健康百科」\n\n交流饮食、运动、睡眠、心理与日常健康知识。\n\n适合发布：个人日常经验、资料整理、健康习惯复盘。涉及疾病、用药和诊断时，请尽量标注信息来源，并以专业医生意见为准。',
    cooked_html: '<h1>关于「健康百科」</h1><p>交流饮食、运动、睡眠、心理与日常健康知识。</p><p>适合发布：个人日常经验、资料整理、健康习惯复盘。涉及疾病、用药和诊断时，请尽量标注信息来源，并以专业医生意见为准。</p>',
    reply_count: 0,
    like_count: 12,
    liked_by_me: false,
    accepted_answer: false,
    vote_score: 12,
    vote_count: 12,
    my_vote: 0,
    share_url: 'http://127.0.0.1:5174/topics/health-wiki-intro/about-health-wiki#post-1',
    deleted_at: null,
    created_at: '2026-05-26T09:00:00+08:00',
    updated_at: '2026-06-02T18:00:00+08:00',
  },
  {
    id: 'post-2',
    topic_id: topic.id,
    user_id: 'u_rain',
    author_name: 'rain_404',
    author_avatar_url: null,
    author_role: 'user',
    author_level: 3,
    author_trust_level: 2,
    author_trust_level_label: '成员',
    parent_id: 'post-1',
    post_number: 2,
    raw_md: '这个版块很适合记录睡眠和运动习惯。',
    cooked_html: '<p>这个版块很适合记录睡眠和运动习惯。</p>',
    reply_count: 0,
    like_count: 3,
    liked_by_me: false,
    accepted_answer: false,
    vote_score: 3,
    vote_count: 3,
    my_vote: 0,
    share_url: 'http://127.0.0.1:5174/topics/health-wiki-intro/about-health-wiki#post-2',
    deleted_at: null,
    created_at: '2026-06-02T18:00:00+08:00',
    updated_at: '2026-06-02T18:00:00+08:00',
  },
];

const related = [
  { ...topic, id: 'health-1', slug: 'screen-height', title: '肩颈不舒服后，我把屏幕垫高了', pinned: false, featured: false, reply_count: 4, view_count: 186, like_count: 9, hot_score: 21.4, tags: ['健康', '办公'], excerpt: '下午脖子紧，后来把视线调平，感觉轻松很多。', last_posted_at: '2026-06-02T17:30:00+08:00' },
  { ...topic, id: 'health-2', slug: 'walk-after-dinner', title: '晚饭后走十分钟，比想象中容易坚持', pinned: false, featured: false, reply_count: 2, view_count: 91, like_count: 6, hot_score: 12.2, tags: ['健康', '散步'], excerpt: '目标很小反而能做下去。', last_posted_at: '2026-06-01T20:20:00+08:00' },
];

function sendJson(res, status, payload) {
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Accept, Authorization, Content-Type, X-ParallelLines-Visitor',
    'Access-Control-Allow-Methods': 'GET, POST, PUT, PATCH, DELETE, OPTIONS',
  });
  res.end(JSON.stringify(payload));
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url ?? '/', 'http://127.0.0.1:8999');
  if (req.method === 'OPTIONS') {
    sendJson(res, 204, {});
    return;
  }

  if (url.pathname === '/api/v1/site/settings') {
    sendJson(res, 200, { data: { settings: { site_title: '平行线', site_tagline: '让答案可追溯', brand_logo_url: '/logo-lines.png', brand_primary_color: '#409EFF' }, updated_at: now } });
    return;
  }

  if (url.pathname === '/api/v1/site/extensions') {
    sendJson(res, 200, { data: [] });
    return;
  }

  if (url.pathname === `/api/v1/topics/${topic.id}`) {
    sendJson(res, 200, { data: topic });
    return;
  }

  if (url.pathname === `/api/v1/topics/${topic.id}/posts`) {
    sendJson(res, 200, { data: posts });
    return;
  }

  if (url.pathname === '/api/v1/boards/health/topics') {
    sendJson(res, 200, { data: related });
    return;
  }

  if (url.pathname === '/api/v1/boards') {
    sendJson(res, 200, { data: [] });
    return;
  }

  sendJson(res, 404, { error: { code: 'not_found', message: `No mock for ${url.pathname}` } });
});

server.listen(8999, '127.0.0.1', () => {
  console.log('mock api listening at http://127.0.0.1:8999/api/v1');
});
