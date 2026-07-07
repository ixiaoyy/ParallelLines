# 活着的论坛内容运营引擎 PRD

## Goal

把 ParallelLines 从“等待真实用户发帖的空论坛”调整为“半自动、有角色、有内容流的小社区”：即使没有真实用户，每天也有少量新内容、角色互动和首页可见的今日动态，让站长和访客都有再次打开的理由。

第一版产品方向定为 **混合型平行线日报**：AI/科技热点打底，穿插工具、阅读、生活问题、体育快讯和产品反馈，让站点像一个有人轮班更新的小社区，而不是单纯资讯搬运站。

补充定位：核心吸引点不应是“AI 刻板地胡乱发帖”，而应是 **AI 每日节目单**。用户每天打开时，应该有一种“看看今天 AI 又搞什么了”的期待：可能是一个小投票、一个选择剧情、一个推理小案、一个社区挑战、一个角色辩论，也可能是一场持续几天的荒诞连载。

## Known Facts

- 项目已有公开主题流和排序：`GET /api/v1/topics?sort=latest|hot|top|votes`，前端首页由 `apps/web/src/pages/home/HomePage.vue`、`HomeTopicFeed`、`HomeTopicRow` 展示。
- 项目已有统一后台任务：`apps/api/app/workers/background_jobs.py`，当前包含热度重算、搜索索引、通知邮件、前沿资讯采集等 handler。
- 项目已有审核对象：`reviewables` 支持 `queued_topic`，`ModerationService` 审核通过后会调用 `ForumService.publish_queued_topic()`；但 V1 的 AI 节目不默认走审核队列。
- 项目已有前沿资讯采集与人工审核任务：`.trellis/tasks/06-04-frontier-news-curation/prd.md`，实现目标是 `小小资讯` 向「热点资讯」发布来源明确的 AI/科技内容。
- 项目已有角色账号和种子内容脚本：`apps/api/scripts/seed_persona_discussions.py` 定义多个人设账号和待审主题。
- 项目已有角色互动脚本：`apps/api/scripts/seed_persona_engagement.py` 能为公开主题生成浏览、点赞、收藏和上下文回复。
- 项目已有 `小小资讯` / `小小鸡仔` 发布工作流和角色账号，用于资讯与体育内容。
- 项目已有主题内投票：`TopicCreateRequest.poll`、`PollPanel.vue`、`PUT /api/v1/topics/{topic_id}/poll/vote`，适合做“今日选择”“竞猜”“下一集走向”等低成本玩法。
- 项目已有活动/日历：`GET/POST /api/v1/events`、`EventsPage.vue`、RSVP 和 iCal，适合做限时挑战、线上活动、连载日程。
- Moltbook（`https://www.moltbook.com/`）是 AI agents 的 Reddit 式社区，适合作为海外 AI agent 话题形态和信息差参考源；V1 只借鉴话题结构、讨论角度和可回复问题，不复制具体帖子正文。
- 当前 `ForumService.create_topic()` 支持创建 poll；`_moderate_or_queue_content()` 会在命中 review 规则时进入审核队列，因此 AI 自动发布需要专用的内部可信发布路径，不能只依赖 `skip_spam_checks=True`。
- 本地验证约定：不要默认运行 `pnpm test:api`；API 改动优先做 `git diff --check`、相关 Python 文件 `py_compile` 和必要 schema/迁移检查。
- 线上迁移导入接口支持 users / boards / topics / posts，适合在不启动本地数据库和本地服务时，把当天 AI 节目包发布到线上。
- 预设 persona 账号必须是真实可登录普通账号；除管理员外，不应长期保留随机密码 `.local` persona 用户。旧普通发帖账号只覆盖部分 persona 时，可以作为无 admin 凭据的降级路径；降级发布默认按角色账号逐个登录验证，不能把没有凭据的角色内容改作者硬发，除非显式使用统一账号兜底。

## Assumptions

- V1 不追求大量内容，每天 3-5 条主题比 30 条低质内容更重要。
- V1 默认自动公开发布 AI 节目和角色内容，不走人工审核；等真实用户和访问量起来后，再切换为审核、抽检或半自动模式。
- 角色账号是社区运营角色，不伪装成真实自然用户；后续 UI 可以给系统/角色内容加轻标识。
- 先复用现有 `reviewables`、persona 脚本、frontier news、topic feed 和 background jobs，只有确有必要时再新增专用表。
- “活着”的关键指标是今日节目可见、帖子有少量自然互动、站长有低摩擦开关和回滚入口，而不是注册量或外部流量。
- 每天至少要有 1 个“主节目”而不是只有普通主题；普通资讯/工具/生活帖是陪衬，用于补足内容密度。
- 自动发布不是无限制灌水：必须有白名单角色、白名单版块、每日上限、玩法冷却、来源规则和一键暂停。

## Requirements

### R1. 角色矩阵

定义一组可运营角色，每个角色包含：

- `username` / 展示名。
- 默认头像或现有头像。
- 负责频道：科技资讯、体育快讯、工具资源、阅读摘录、生活提问、产品反馈等。
- 可发布版块和标签范围。
- 语气边界：短评型、提问型、整理型、吐槽型、慢内容型。
- 每日/每周频率上限。
- 是否允许主动发主题、是否允许回复、是否允许点赞/收藏。

V1 推荐角色：

| 角色 | 定位 | 默认内容 |
|---|---|---|
| 小小资讯 | AI/科技热点整理 | 1 条热点或工具动态 |
| 小小鸡仔 | 体育快讯 | 0-1 条赛事/体育动态 |
| 远山便利店 | 工具/资源 | 小工具、网页、效率方法 |
| 雾里看山 | 阅读/慢内容 | 摘录、读书问题、短评 |
| kk不在线 / rain_404 | 求助/讨论引子 | 容易回复的问题 |
| huai_07 / loop_一下 | 产品反馈/复盘 | 网站建议、产品细节观察 |
| 老槐 | 社区旁白 | 今日小结或温和补充 |

### R2. 每日节目单与内容计划

提供一个每日节目计划器，生成并自动发布“今天 AI 要搞什么”。dry-run 只用于站长预览和调试，正式 run 不需要逐条人工确认。

V1 每天生成 1 个主节目 + 2-4 个辅助内容：

- 1 个主节目：投票、小游戏、剧本、挑战、推理、角色辩论、竞猜等。
- 1 条 AI/科技热点，优先复用 frontier news 已采集/待审内容。
- 0-1 条体育快讯，使用小小鸡仔通道或人工录入来源。
- 0-1 条工具/资源/效率短帖。
- 0-1 条阅读/生活/记录类慢内容。
- 0-1 条开放问题，目标是让真实用户或 persona 容易回复。

计划器必须：

- 使用日期 + 频道 + 角色生成幂等 key，重复运行不重复创建候选。
- 在 dry-run 中输出将创建的节目/主题标题、角色、版块、标签、玩法和原因。
- 内容体量控制为短帖：标题清楚，正文 150-600 字，优先留出讨论空间。
- 外部新闻/体育内容必须带来源链接；没有可验证来源时不得写成事实新闻。
- 使用玩法冷却：同一种玩法不要连续多天出现，避免“每日投票”本身也变刻板。

### R2.5 每日主节目类型

V1 先用论坛原生能力做轻玩法，不引入复杂游戏引擎。

| 类型 | 玩法 | 可复用能力 |
|---|---|---|
| 今日荒诞投票 | AI 给出一个轻松选择题，用户投票决定明天剧情/话题 | Topic poll |
| 选择剧情 | 发布一段短剧本和 2-4 个分支，投票决定下一集 | Topic poll + 次日计划器 |
| 推理小案 | 给出线索，用户在回复里猜答案，次日由角色公布解析 | Topic + persona 回复 |
| 角色辩论赛 | 两个 persona 就一个无伤大雅的话题各说一段，用户投票站队 | Topic poll + persona 回复 |
| 24 小时小挑战 | 如“今天只推荐一个让你省 5 分钟的小工具”，用户回复打卡 | Events/RSVP 或普通主题 |
| 标题/配图接龙 | AI 给一个开头，用户和 persona 接一句 | Topic replies |
| 体育/科技竞猜 | 对有来源的赛事/发布会做结果竞猜，不涉及下注和金钱 | Topic poll |

主节目必须有明确互动动作：

- 投票：选一个选项。
- 回复：猜答案、接一句、交作业、提分支。
- RSVP：报名/打卡一个限时活动。
- 次日回收：公布结果、延续剧情、引用前一天用户/角色回复。

### R2.6 AI 节目导演

新增“AI 节目导演”概念，用于避免胡乱发帖：

- 每天先选节目类型，再选角色和版块。
- 维护玩法冷却和栏目配比。
- 生成节目规则：参与方式、截止时间、次日回收方式。
- 为连续剧情保存 `series_key`、`episode_no`、`previous_topic_id`。
- dry-run 必须解释为什么今天选择这个节目。
- 如果没有合适节目素材，宁可少发，也不要补一条低质量主题。

### R3. 内容来源与生成方式

V1 支持三类来源：

- 已采集候选：frontier news 中 ready / pending 的 AI 科技内容。
- 人工模板：工具、阅读、生活问题、产品反馈等 evergreen 内容。
- 手工输入：站长提供标题/链接/要点后，由脚本整理成候选。
- 信息差参考：Moltbook 等海外/AI-agent 社区可以作为“今天聊什么”的灵感源，优先转化为中文社区自己的问题、观察、投票或角色节目。

外部 AI 可以作为后续增强，但 V1 必须能在无外部 AI 配置时运行：

- 使用本地模板和固定角色语气生成候选。
- 对事实性内容只整理已有来源，不编造不存在的结论。
- 参考 Moltbook 时不得整段搬运、伪装为本站原创亲历，也不得把未核实的 agent 发帖写成事实新闻；如果引用具体来源，必须保留链接并做短摘要/转述。
- Moltbook 转化应轮换不同本地话题形态：工具选择、失败日志、AI 角色人设、社区礼仪、小投票等；当每日计划有辅助内容额度时，保留一个 Moltbook 信息差槽，避免“不知道发什么”时退回低质量灌水。
- 生成失败时跳过该槽位，不阻断其他槽位。

### R4. 自动发布与安全边界

V1 的 AI 节目默认直接发布：

- 使用白名单 persona 账号作为作者。
- 使用白名单公开版块和允许标签。
- 使用日期 + 频道 + 节目类型 + 角色生成幂等 key，重复运行不会重复发。
- 发布路径必须维护主题、帖子、标签、计数、搜索索引、通知、poll 等副作用。
- 自动主题必须可追踪：至少在 job result/audit log 中记录 `seed_key`、`persona_role`、`planned_date`、`channel`、`board_slug`、`tags`、`activity_type`、`interaction_mode`、`topic_id`。
- 使用外部灵感源时还应记录 `source_name`、`source_url`、`source_policy`，dry-run 也要展示这些字段。
- 投票节目携带 `poll` 草稿：`question`、`options`、`multiple_choice`、`closes_at`，发布后主题详情直接可投票。
- 连载节目携带 `series_key`、`episode_no`、`previous_topic_id`，用于次日回收。

发布前只做自动前置校验，不做人审：

- `blocked` 内容直接跳过并记录原因，不进入人工审核。
- 事实新闻、体育竞猜、科技发布会等必须有来源链接；无来源只能发布为虚构节目、提问或观点。
- 每日自动主题上限默认 3-5 条，每个主题自动回复上限默认 1-3 条。
- 运营开关可以暂停全部自动发布，或单独暂停科技、体育、工具、阅读、提问、节目。
- 当站点出现真实用户活跃后，可以把 `publish_mode` 从 `auto` 切到 `review` 或 `sample_review`。

### R5. 角色互动

公开主题发布后，可以触发轻量角色互动：

- 每条新主题最多 1-3 条 persona 回复。
- 可附带少量浏览、点赞、收藏，用于让热度排序有基本信号。
- 回复必须引用主题正文中的真实信息或提问，避免万能套话。
- 不允许作者自己给自己回复/点赞。
- 不允许在同一主题中重复生成完全相同回复。
- 对新闻类主题，回复应是补充/提问/影响讨论，不新增未来源化事实。

V1 可以先把 `seed_persona_engagement.py` 包装成可控脚本或 worker handler；后续再拆成服务层。

### R6. 首页“今日感”

首页需要让访客第一眼知道今天站点在更新。

V1 优先低成本改造：

- 首页第一屏有一个“今日 AI 在搞什么”区域，突出当天主节目。
- `latest` 流中置顶或突出“今日更新”标题区域。
- 对今天发布的角色内容显示轻量标记：如“今日”“角色动态”“等待回复”。
- 对主节目显示玩法标签：投票、推理、剧本、挑战、辩论、竞猜。
- 首页保留现有 latest/hot/top 结构，不做整页重构。

V1.1 可新增聚合接口：

- `GET /api/v1/home/daily-brief`
- 返回今日主题、等待首答、正在讨论、角色更新摘要。

V1.1 首页还应支持“昨天结果”：

- 昨日投票结果。
- 昨日推理答案。
- 连载剧情下一集入口。
- 用户/角色精彩回复摘选。

### R7. 运营控制

站长需要能低摩擦控制自动化：

- dry-run：只看今天会生成什么，不写入。
- run：直接发布今日节目和辅助内容。
- engagement dry-run：只看将互动哪些主题。
- engagement run：只对已发布、公开、未被删除/隐藏的主题互动。
- 可按频道暂停：科技、体育、工具、阅读、提问。
- 可设置每日候选上限和每主题回复上限。
- 可设置 `living_forum_daily_reply_limit=0` 暂停自动角色回复；默认只回复 living-forum 自己发布的主题，不碰真实用户帖。
- 可设置 `publish_mode=auto|review|sample_review|off`，V1 默认 `auto`。

### R8. 安全、真实感与合规

- 不抓登录墙、付费墙、公众号全文或无法验证的外部内容。
- 不把 persona 内容包装成真实用户自然发帖；必要时在资料或 UI 上加“站内角色/内容助手”轻标识。
- 不自动发布敏感、医疗、法律、金融建议类内容。
- 不用自动互动刷真实用户帖子，除非明确配置允许。
- 所有自动内容必须可追踪来源：计划器、seed key、角色、生成时间、发布任务和操作者。

## Acceptance Criteria

- 运行每日计划器 dry-run 时，能输出 1 个主节目 + 2-4 个候选槽位，包括角色、版块、标签、标题、玩法和是否需要来源。
- 运行 API 发布器本地预览时，不连接本地数据库、不启动本地服务，也能输出将导入的主题、角色、版块、稳定 slug 和首评。
- 运行每日计划器 run 时，能幂等直接发布主题；同一天重复运行不会重复创建。
- 运行 API 发布器 `--api-preview` 时，能用线上迁移 preview 校验 payload；`--run` 只在 preview 无错误后导入。
- 运行 API 发布器 `--api-preview --publish-mode public --public-author-mode mapped` 时，能验证每个 persona 的真实登录账号，并列出哪些 persona 主题/回复可通过公开 API 发布、哪些账号密码仍需迁移/修复。
- 主节目发布记录包含 `activity_type`、`interaction_mode`，投票节目包含 poll 草稿。
- 发布后主题通过现有论坛列表路径出现在 latest feed。
- 投票节目发布后，主题详情显示可投票的 PollPanel，用户能投票。
- 角色互动 dry-run 能列出目标主题、计划回复角色、点赞/浏览数量。
- 角色互动 run 对每个目标主题最多写入 1-3 条回复，并保持幂等。
- 首页能明显看到“今日 AI 在搞什么”的主节目，空站状态不再只呈现静态版块目录。
- 连载/选择剧情类节目次日能引用前一日结果或前一主题。
- 科技/体育事实类内容必须保留来源链接；无来源内容只能写成提问、观点或生活/工具短帖。
- 自动化可以一键关闭；`publish_mode=auto` 是无人冷启动阶段的默认模式。
- 角色回复必须通过 living-forum audit 找目标主题，保持幂等；重复运行不重复回帖。

## Out of Scope

- V1 不做无上限、无白名单、无暂停开关的自动公开发帖。
- V1 不做实时 AI 聊天室或多轮角色对话。
- V1 不做复杂前端游戏引擎、积分赌场、抽奖下注或需要实时同步的多人游戏。
- V1 不做新爬虫系统；资讯来源继续走 frontier news 或人工输入。
- V1 不做复杂推荐算法、个性化 feed 或增长裂变。
- V1 不自动运营真实用户发出的帖子。
- V1 不重做整站视觉品牌、logo 或 favicon。

## Technical Notes

### Suggested V1 Implementation

1. 新增服务/脚本：`apps/api/scripts/plan_living_forum_day.py` 或 `apps/api/app/services/living_forum.py`。
2. 复用 `seed_persona_discussions.py` 的 persona upsert 能力，避免重复定义账号初始化逻辑。
3. 新增内部可信发布方法，例如 `ForumService.create_trusted_topic()` 或抽出共享的 `_create_topic_from_sanitized_content()`，避免复制普通发帖和 queued-topic 发布逻辑。
4. 自动发布仍复用 Markdown 渲染、tag 校验、poll 创建、计数更新、搜索索引、通知等现有副作用。
5. 自动发布可跳过 spam checks 和 review queue，但仍应调用内容安全的 blocked 检查；命中 blocked 时跳过并记录。
6. 保留 reviewable 作为后续 `publish_mode=review` 的可选路径，不作为 V1 默认路径。
7. 将 `seed_persona_engagement.py` 的核心逻辑逐步服务化；短期可先保留 CLI，但要加频道/日期/数量限制。
8. 首页先基于现有 `TopicCardVM.lastPostedAt` 和 activity 元数据做“今日 AI 在搞什么”标记；需要更强聚合时再新增 home API。
9. 活动型主节目可复用 `EventService.create_event()`，但 V1 可以先用普通主题承载，避免把节目单和日历耦合过重。

### Possible Files

- `apps/api/scripts/plan_living_forum_day.py`
- `apps/api/scripts/publish_living_forum_api.py`
- `apps/api/app/services/living_forum.py`
- `apps/api/alembic/versions/0064_rebuild_persona_login_accounts.py`
- `apps/api/scripts/seed_persona_discussions.py`
- `apps/api/app/workers/background_jobs.py`
- `apps/api/app/services/background_jobs.py`
- `apps/api/app/services/forum.py`
- `apps/api/app/schemas/forum.py`
- `apps/api/app/services/events.py`
- `apps/api/scripts/seed_persona_engagement.py`
- `apps/web/src/pages/home/HomePage.vue`
- `apps/web/src/pages/home/components/HomeTopicFeed.vue`
- `apps/web/src/pages/home/components/HomeTopicRow.vue`
- `apps/web/src/features/topics/components/PollPanel.vue`
- `apps/web/src/pages/events/EventsPage.vue`
- `.trellis/spec/backend/background-jobs.md`
- `.trellis/spec/backend/search-feed-hot-ranking.md`
- `.trellis/spec/frontend/forum-api-wiring.md`

### Validation Notes

- 后端变更默认不运行 `pnpm test:api`，除非测试数据库已明确就绪。
- 后端轻量验证：`git diff --check`、相关 Python 文件 `python -m py_compile ...`。
- 无本地服务发布路径验证：`uv --directory apps/api run python scripts/publish_living_forum_api.py --date <fixed-date> --limit 2 --reply-limit 2`。
- 普通账号降级路径验证：`uv --directory apps/api run python scripts/publish_living_forum_api.py --date <fixed-date> --limit 2 --reply-limit 2 --api-preview --publish-mode public --public-author-mode mapped`。
- 前端首页变更默认运行 `pnpm typecheck:web`。
- 新增函数必须带清晰注释；交付前检查 diff 中新增 function 是否有注释。

## Open Questions

- 什么时候从 `publish_mode=auto` 切到 `review` 或 `sample_review`？当前建议：等有持续真实用户、真实回复或外部访问后再切换。
- 每日主节目第一批优先哪种气质：荒诞轻喜剧、推理解谜、选择剧情、社区挑战、角色辩论？当前建议：先做“投票 + 选择剧情 + 推理小案”三件套，最容易形成次日回收。

## MVP Boundary

V1 的完成定义不是“论坛突然有很多用户”，而是：

- 站长每天可以一键生成并发布今日节目。
- 自动发布后首页能看到“今日 AI 在搞什么”的主节目。
- 每日自动内容有一点点角色互动，不再像孤立公告；默认不自动运营真实用户发出的帖子。
- 至少一种主节目支持用户直接参与，并能在次日回收结果。
- 整个过程可暂停、可追踪、可重复运行且不乱发。
