# Discourse 级论坛能力补齐路线图

## Goal

对照 `D:\work\discourse`，将 ParallelLines 从论坛 MVP 补齐到可公开运营论坛，再逐步靠近 Discourse 生态。

## Current Baseline

- ParallelLines 当前约 41 个 API 路由、13 个模型、6 个 service、7 个 migration、1 个主要 worker。
- Discourse 本地约 137 个 controller、353 个 model、165 个 service、222 个 job、230 个 serializer、1688 个 migration、43 个插件。

## Execution Order

### P0

- `05-18-public-invite-boards` — 公共/邀请制版块、ACL 与邀请流程：已有任务：实现私密/邀请版块访问控制、邀请生命周期和左侧分组。
- `05-20-account-recovery-security` — 账号找回与登录安全：补齐忘记密码、修改密码/邮箱、登录设备管理、2FA 和 OAuth/SSO 基础能力。
- `05-20-admin-site-settings-user-management` — 后台站点设置、用户管理与系统面板：从单一审核台扩展为可运营后台：用户管理、站点设置、系统健康、邮件日志与审计。
- `05-20-anti-spam-rate-limits-screening` — 反垃圾、频控与屏蔽名单：实现发帖/注册/举报等关键路径的频控、IP/邮箱/URL 屏蔽、自动禁言和信任边界。
- `05-20-background-job-scheduler` — 后台任务队列、重试与定时调度：建立可靠后台任务体系，承载邮件、通知、索引、清理、备份和统计等异步工作。
- `05-20-backup-restore-export` — 备份、恢复与数据导出：实现论坛数据备份、恢复、下载导出与管理员可用的灾备流程。
- `05-20-email-notifications-digests-inbound` — 邮件通知、摘要邮件与入站回复：补齐真实论坛的邮件触达：通知邮件、摘要邮件、退信处理和邮件回复入站。
- `05-20-full-text-search-engine` — 正式全文搜索与搜索分析：从 SQL LIKE 升级为可运营全文搜索，支持索引、相关性、权限过滤和搜索日志。
- `05-20-moderation-reviewable-workflow` — 审核 Reviewable 工作流与申诉：在基础举报队列之上建立统一审核对象、分配、认领、处理理由、自动规则和申诉机制。
- `05-20-post-revisions-history` — 帖子编辑历史、版本对比与恢复：记录帖子编辑版本，支持作者/版主查看差异、恢复版本和审计编辑行为。
- `05-20-topic-lifecycle-move-merge-split` — 主题生命周期：关闭、置顶、移动、拆分与合并：补齐真实论坛主题管理操作，包括状态控制、跨版块移动、拆分回复、合并主题和审计。
- `05-20-uploads-avatars-attachments` — 上传、头像与附件存储：补齐图片/文件上传、头像上传、附件引用、存储清理与 CDN/S3 兼容能力。

### P1

- `05-20-api-keys-webhooks` — API Key、Webhook 与外部系统接入：提供安全的 API key、作用域、Webhook 事件投递、签名和重试机制。
- `05-20-badges-trust-levels` — 徽章与信任等级体系：在积分经验之外，建立可运营的徽章、信任等级和自动授权规则。
- `05-20-board-management-required-tags` — 版块管理、子版块、必填标签与默认策略：扩展版块能力：子版块、版主、默认通知、必填标签、发帖模板和版块设置。
- `05-20-notification-preferences-tracking` — 通知偏好、跟踪状态与免打扰：补齐 watching/tracking/muted、邮件/站内偏好、免打扰和已读游标。
- `05-20-privacy-data-retention-anonymization` — 隐私、数据保留、匿名化与账号删除：提供真实社区需要的数据隐私能力：导出、匿名化、账号删除、保留策略和日志脱敏。
- `05-20-public-api-docs-openapi-client` — 公开 API 文档、客户端生成与兼容策略：将当前内部 API 整理成可维护公开契约，支持 OpenAPI client、版本、弃用和示例。
- `05-20-rich-composer-onebox-emoji` — 富文本编辑器、Onebox、表情与代码体验：升级发帖/回复体验：拖拽上传、预览、链接展开、表情、代码高亮和引用体验。
- `05-20-seo-permalinks-sitemap` — SEO、永久链接、Sitemap 与分享元数据：补齐公开论坛可被搜索引擎和社交平台正确索引/分享的能力。
- `05-20-server-side-drafts` — 服务端草稿与多端恢复：将当前浏览器本地草稿升级为服务端草稿，支持新主题/回复多设备同步和恢复。
- `05-20-site-theme-i18n-branding` — 站点主题、品牌配置与文案国际化：支持管理员配置 Logo、色板、站点文案、主题和多语言基础。
- `05-20-social-actions` — 社区互动动作补齐：点赞、收藏、转发与邀请入口：已有任务：补齐点赞、收藏、分享入口及登录态/通知联动。
- `05-20-topic-solved-voting-polls` — 已解决、投票、问答与 Poll 能力：补齐常见技术论坛互动模式：解决方案标记、主题/帖子投票、问答排序和投票组件。
- `05-20-user-points-experience` — 用户积分与经验成长体系：已有任务：补齐积分、经验、成长规则和展示。
- `05-20-user-profile-settings-directory` — 用户设置、公开目录与个人资料完善：扩展用户中心：资料编辑、偏好设置、公开用户目录、隐私设置和活动页。
- `05-20-user-social-relationships-pm` — 用户关注、忽略/屏蔽与私信：实现用户关系和私密交流能力：关注用户、忽略/屏蔽用户、私信主题。

### P2

- `05-20-ai-forum-assistant` — AI 摘要、推荐与审核辅助：为长主题摘要、相似主题推荐、自动标签和审核辅助预留 AI 能力。
- `05-20-analytics-data-explorer-reports` — 数据报表、运营分析与 Data Explorer：补齐运营报表、趋势分析、管理员查询和导出能力。
- `05-20-calendar-events` — 日历、活动与本地时间：支持社区活动、日历订阅、时区本地化和提醒。
- `05-20-chat-presence` — 实时 Chat、在线状态与 Presence：实现论坛内即时聊天、在线用户、输入状态和实时频道。
- `05-20-external-integrations` — GitHub、Zendesk、Patreon 等外部集成：实现常见社区外部集成框架和若干 provider。
- `05-20-import-export-migration-tools` — 导入、导出与迁移工具：支持从其他论坛/CSV/Markdown 导入数据，以及面向迁移的导出工具。
- `05-20-localization-multilingual-content` — 多语言内容、本地化与翻译工作流：支持多语言 UI、内容本地化、翻译覆盖和语言偏好。
- `05-20-mobile-push-pwa` — 移动端适配、PWA 与推送通知：提升移动端论坛体验，支持 PWA 安装、离线页和 Web Push。
- `05-20-plugin-extension-system` — 插件扩展系统与事件 Hook：设计可扩展插件点、事件 hook、前端插槽和安全边界，为生态功能预留入口。
- `05-20-subscriptions-payments` — 订阅、付费会员与支付集成：为付费社区预留订阅、会员权益、支付 webhook 和账单能力。
- `05-20-theme-marketplace` — 主题市场、组件安装与安全沙箱：支持安装/更新/回滚主题和主题组件，并隔离不可信代码风险。

## Operating Rules

- 每次只 start 一个子任务，完成实现/测试/spec 更新后再进入下一个。
- P0 先保证安全、运营和数据可靠；P1 补齐正常论坛体验；P2 做生态和高级能力。
- 已存在任务不重复创建：邀请版块、互动动作、积分经验已纳入本 roadmap。
