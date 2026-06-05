# 前沿资讯采集与人工审核 PRD

## Goal

为「前沿资讯」板块建立一个低风险、高信号的内容候选池：系统定时从白名单 RSS / 官方 API / 官方博客抓取候选资讯，经管理员人工审核、编辑后发布为论坛主题。

## Known Facts

- 项目已有统一后台任务框架：`apps/api/app/workers/background_jobs.py` 与 `BackgroundJobService`。
- 项目已有发帖服务：`ForumService.create_topic()` 会维护主题、帖子、标签、计数、搜索索引与通知等副作用。
- 项目已有同步官方帖的幂等样例：`apps/api/app/services/quality_posts.py`。
- 本项目本地测试约定：不默认运行 `pnpm test:api`；后端轻量验证优先 `git diff --check`、相关 Python 文件 `py_compile`、必要迁移/schema 检查。

## Assumptions

- 第一版只做「采集候选 + 人工审核发布」，不做自动公开发布。
- 内容定位以 AI / ML / AI 工具 / 前沿科研为主。
- 发布目标板块固定为 `frontier` / 「前沿资讯」。
- 发布作者固定使用「小小资讯」账号；系统初始化时幂等自动创建为普通用户。
- 定时任务负责采集与 AI 整理；管理员只审核最终候选，不需要手工翻译。

## Requirements

### R1. 来源白名单

系统支持配置来源：

- `rss`：官方博客、媒体 RSS、技术博客。
- `arxiv`：按分类或查询抓取 arXiv 元数据。
- `hn`：Hacker News top / best / new story 列表。
- `github_search`：按 topic / stars / pushed / created 查询仓库。
- `github_releases`：盯固定仓库 release。
- `manual`：管理员手动粘贴 URL 建候选。

第一版默认启用来源不超过 20 个，避免信息过载。

### R2. 候选入库与去重

每条外部内容统一规范化为 `news_items`：

- 标题、原始链接、规范化链接、来源、发布时间、作者/组织、原始摘要、建议标签、抓取时间。
- 按 `source_id + external_id` 和 `canonical_url_hash` 双重去重。
- 重复内容不创建新的待审候选。

### R2.5 AI 初审、识别、翻译与中文整理

候选入库后，后台任务异步调用 AI 做初审与中文整理，输出给管理员审核：

- 识别「这是什么」：模型发布、研究论文、开源工具、产品功能、行业新闻、安全/政策、教程/案例、硬件/算力、其他。
- 生成中文标题建议，不夸大、不标题党。
- 翻译并整理 3-5 条中文要点。
- 生成「为什么值得关注」中文段落，明确影响对象：开发者、研究者、产品/创业者、普通用户等。
- 生成建议标签，如 `AI`、`LLM`、`Agent`、`论文`、`开源工具`、`多模态`、`机器人`。
- 生成可信度/风险提示：官方来源、社区讨论、二手报道、付费墙、信息不足、疑似营销等。
- 输出审核建议：`ready` / `needs_edit` / `low_signal` / `reject_suggested`。

AI 输出只作为草稿，不能自动发布；管理员发布前必须能编辑标题、正文和标签。

### R3. 人工审核流

管理员可以在后台：

- 查看待审核候选列表。
- 按来源、状态、标签、分数过滤。
- 查看原文链接和系统抓取的摘要。
- 查看 AI 识别结果、中文标题建议、中文摘要、风险提示。
- 编辑发布标题、摘要、标签、正文；AI 生成内容只做默认草稿。
- 发布、驳回、标记重复、稍后处理。
- 禁用低质量来源。

### R4. 发布

发布时必须走论坛发帖服务，而不是直接插入 `topics/posts`：

- 调用 `ForumService.create_topic()` 创建主题，确保计数、搜索、通知、插件事件等一致。
- 创建主题的 `board_slug` 固定为 `frontier`。
- 创建主题的 `current_user` 为「小小资讯」账号；审核人记录在 `news_items.approved_by_id`。
- 发帖正文必须保留来源、原文链接、发布时间。
- 正文只保存摘要/评论/链接，禁止搬运全文、PDF 或大段付费内容。

### R4.5 小小资讯账号初始化

系统初始化/迁移种子阶段必须幂等确保「小小资讯」普通用户存在：

- `username`: `小小资讯`
- `display_name`: `小小资讯`
- `email`: 默认 `frontier-news-bot@parallellines.local`，允许通过配置覆盖。
- `role`: `user`，禁止赋予 `moderator` 或 `admin`。
- `status`: `active`，以便复用现有公开板块发帖服务。
- `level`: `0`，`trust_level`: `0`。
- `hashed_password`: 使用随机高强度不可恢复密码生成并哈希保存；系统不展示、不记录、不发送该密码。
- 不创建登录 session、邮箱验证码、API key 或 webhook token。
- 若同名/同邮箱用户已存在且不是该机器人，应初始化失败并记录明确错误，避免劫持已有真实用户。
- 该账号只用于系统发布审核后的资讯主题；审核、驳回和编辑权限仍以管理员账号为准。

### R5. 安全与合规

- 只采集白名单来源，优先 RSS/API。
- 不绕过 robots.txt、登录墙、付费墙或反爬限制。
- 保留来源与原文链接。
- HTTP 请求必须有超时、User-Agent、错误记录、限频。
- arXiv 只存元数据/摘要/abstract 链接，不转存 PDF 或源码。

## Data Model Draft

### `news_sources`

| Field | Purpose |
|---|---|
| `id` | 主键 |
| `key` | 稳定来源 key，如 `openai_news` |
| `name` | 展示名 |
| `kind` | `rss` / `arxiv` / `hn` / `github_search` / `github_releases` / `manual` |
| `url` | RSS URL、API URL 或页面 URL |
| `config` | JSON 配置：查询、标签、阈值等 |
| `enabled` | 是否启用 |
| `trust_level` | `official` / `research` / `community` / `media` |
| `fetch_interval_minutes` | 抓取间隔 |
| `last_checked_at` | 最近抓取时间 |
| `last_error` | 最近错误摘要 |
| `created_at/updated_at` | 时间戳 |

### `news_items`

| Field | Purpose |
|---|---|
| `id` | 主键 |
| `source_id` | 来源 |
| `external_id` | RSS guid、arXiv id、HN id、GitHub repo/release id |
| `canonical_url` | 规范化原文链接 |
| `canonical_url_hash` | 去重索引 |
| `title` | 原始标题 |
| `summary` | 原始摘要或系统摘要 |
| `author_names` | 作者/组织 |
| `published_at` | 外部发布时间 |
| `suggested_tags` | JSON 标签 |
| `item_type` | AI 识别类型：model_release / paper / tool / product / industry_news 等 |
| `ai_title_zh` | AI 生成中文标题草稿 |
| `ai_summary_zh` | AI 生成中文摘要 |
| `ai_key_points` | AI 生成中文要点 JSON |
| `ai_why_it_matters` | AI 生成「为什么值得关注」 |
| `ai_risk_flags` | AI 风险/合规提示 JSON |
| `ai_review_suggestion` | `ready` / `needs_edit` / `low_signal` / `reject_suggested` |
| `ai_model_name` | AI 整理使用的模型/算法名 |
| `ai_cost_units` | 成本统计单位 |
| `ai_processed_at` | AI 整理完成时间 |
| `ai_error` | AI 整理失败摘要 |
| `score` | 排序分 |
| `status` | `collected` / `ai_pending` / `pending` / `needs_edit` / `published` / `rejected` / `duplicate` / `failed` |
| `review_notes` | 审核备注 |
| `approved_by_id/approved_at` | 审核人和时间 |
| `topic_id` | 发布后的主题 ID |
| `raw_payload` | 原始响应精简 JSON |
| `created_at/updated_at` | 时间戳 |

### `news_ai_runs`

| Field | Purpose |
|---|---|
| `id` | 主键 |
| `news_item_id` | 候选资讯 |
| `status` | `succeeded` / `failed` |
| `provider` | `local` / `openai` / `anthropic` / `other` |
| `model_name` | 模型名或本地算法名 |
| `input_tokens/output_tokens/cost_units` | 成本统计 |
| `prompt_version` | 提示词版本 |
| `error` | 错误摘要 |
| `created_at` | 运行时间 |

## API Draft

Admin-only:

- `GET /api/v1/admin/news-sources`
- `POST /api/v1/admin/news-sources`
- `PUT /api/v1/admin/news-sources/{source_id}`
- `POST /api/v1/admin/news-sources/{source_id}/test`
- `POST /api/v1/admin/news-sources/{source_id}/collect`
- `GET /api/v1/admin/news-items?status=&source=&limit=`
- `GET /api/v1/admin/news-items/{item_id}`
- `PUT /api/v1/admin/news-items/{item_id}`
- `POST /api/v1/admin/news-items/{item_id}/ai-refresh`
- `POST /api/v1/admin/news-items/{item_id}/publish`
- `POST /api/v1/admin/news-items/{item_id}/reject`
- `POST /api/v1/admin/news-items/{item_id}/duplicate`

## Admin UI Draft

新增后台页：「资讯审核」。

列表卡片显示：

- 标题、来源、发布时间、抓取时间。
- 推荐标签、评分、状态。
- 原文链接。
- 操作：预览、发布、驳回、重复、禁用来源。

详情侧栏：

- 左侧：原始候选信息。
- 中间：AI 识别结果、中文摘要、风险提示、审核建议。
- 右侧：可编辑的论坛发帖标题、标签、正文预览。

## Publish Template

```md
> 自动收集候选，经人工审核发布。请以原文为准。

**来源**：{source_name}
**发布时间**：{published_at}
**原文链接**：{canonical_url}
**类型**：{item_type_zh}

## 摘要

- {ai_key_point_1}
- {ai_key_point_2}
- {ai_key_point_3}

## 为什么值得关注

{ai_why_it_matters_or_reviewer_note}

## 审核备注

{optional_reviewer_note}
```

## AI Prompt Contract

输入只包含白名单来源元数据、原始摘要/abstract、有限正文摘录和原文 URL；不输入登录后内容、付费全文或大段未授权正文。

输出必须是结构化 JSON：

```json
{
  "item_type": "paper",
  "title_zh": "中文标题建议",
  "summary_zh": "100-200 字中文摘要",
  "key_points": ["要点 1", "要点 2", "要点 3"],
  "why_it_matters": "为什么值得关注",
  "suggested_tags": ["AI", "论文"],
  "risk_flags": ["official_source", "needs_human_check"],
  "review_suggestion": "ready"
}
```

硬性规则：

- 不得编造原文没有的信息。
- 不得输出夸大式标题。
- 信息不足时必须输出 `needs_edit` 或 `low_signal`。
- 付费墙、无来源、疑似营销内容默认 `needs_edit` 或 `reject_suggested`。
- AI 整理失败不阻断候选入库，状态保留为 `needs_edit` 并显示错误。

## Initial Source Pool

优先从这些来源开始：

- OpenAI News
- Anthropic News
- Google DeepMind Blog
- Hugging Face Blog
- NVIDIA Developer Blog / RSS
- Microsoft Research Blog
- GitHub Changelog
- arXiv: `cs.AI`, `cs.LG`, `cs.CL`, `cs.CV`, `stat.ML`
- Hacker News `topstories` / `beststories`
- GitHub Search: `topic:llm`, `topic:ai-agent`, `topic:rag`, `topic:computer-vision`
- InfoQ AI

## Scoring Draft

- 官方来源：+30
- 研究来源：+25
- 社区来源：+10
- 7 天内：+10
- 标题或摘要命中 AI/LLM/Agent/RAG/多模态/机器人/开源模型等关键词：+5 到 +20
- HN 高分或 GitHub 高 star/近期活跃：+5 到 +20
- 缺少原文链接：拒绝
- 付费墙、转载站、无来源、疑似标题党：降权或拒绝

## Acceptance Criteria

- 管理员能配置至少 3 类来源：RSS、arXiv、HN/GitHub 之一。
- 定时任务能抓取候选并幂等入库。
- 定时任务能为新候选生成 AI 中文整理草稿，失败时可重试且不影响采集。
- 重复 URL/guid 不会重复生成候选。
- 管理员能编辑候选并发布到「前沿资讯」板块。
- 发布到固定 `frontier` 板块，发布作者为「小小资讯」，审核人单独记录。
- 发布后的主题包含来源、原文链接和审核说明。
- 驳回/重复/发布状态可追踪。
- 来源抓取失败不会中断其他来源，并能在后台看到错误。

## Out of Scope

- 第一版不做全网搜索爬虫。
- 第一版不自动公开发布。
- 第一版不抓登录后内容、付费内容、公众号全文。
- 第一版不做复杂推荐算法。
- 第一版不转存论文 PDF、网页全文或图片素材。

## Technical Notes

- 后台任务应接入现有统一 worker，而不是新增独立 daemon。
- 新增任务名建议：`collect_frontier_news`。
- 新增任务名建议：`enrich_frontier_news_item`，由采集任务为新候选逐条入队。
- 新增配置建议：`BACKGROUND_FRONTIER_NEWS_INTERVAL_SECONDS`。
- 新增配置建议：`FRONTIER_NEWS_BOARD_SLUG=frontier`。
- 新增配置建议：`FRONTIER_NEWS_BOT_USERNAME=小小资讯`。
- 新增配置建议：`FRONTIER_NEWS_BOT_EMAIL=frontier-news-bot@parallellines.local`。
- 新增配置建议：`FRONTIER_NEWS_AI_PROVIDER`、`FRONTIER_NEWS_AI_MODEL`、`FRONTIER_NEWS_AI_ENABLED`。
- 发布路径复用 `ForumService.create_topic()`。
- AI 调用只能发生在后台 worker 或管理员显式刷新动作中，不得在普通公开请求路径同步调用外部 AI/network。
- 如果未配置外部 AI，必须提供本地 deterministic fallback：翻译留空、生成基础中文模板并标记 `needs_edit`。

## Open Questions

- AI 供应商与模型待定；实现时应做 provider 抽象，避免把具体模型写死在业务逻辑里。
