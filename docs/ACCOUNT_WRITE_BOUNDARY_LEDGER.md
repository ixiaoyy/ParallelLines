# 主站账号写入边界、外键与事务台账（阶段 1 · 同进程收口）

核对日期：2026-11-23。依据 `SHARED_SERVICES_EXTRACTION_PLAN.md` 阶段 1 要求，基于 `ParallelLines/apps/api/app/` 当前源码静态核查整理。本阶段**不改表结构、不切流量、不改变既有 API 与会话语义**，目标是为账号域建立精确写权台账与防越界静态守卫。

---

## 1. 账号与权益域核心表（7 张）

| 表名 | 模型类 | 责任归属 |
| --- | --- | --- |
| `users` | `User` | 账号核心身份、凭据、2FA、状态、平台角色（当前亦混存部分社区成长/资料字段） |
| `user_sessions` | `UserSession` | 主站会话生命周期与撤销 |
| `email_verification_codes` | `EmailVerificationCode` | 邮箱验证码生命周期 |
| `user_security_tokens` | `UserSecurityToken` | 密码重置、邮箱变更、Chat SSO / Unified Auth / FableSpace 一次性安全票据 |
| `user_recovery_codes` | `UserRecoveryCode` | 2FA 恢复码 |
| `product_access_grants` | `ProductAccessGrant` | 跨产品准入与显式权益授予/到期/撤销 |
| `user_point_events` | `UserPointEvent` | 账户积分/成长事件（属社区成长与账号交界表，后续按需归社区域） |

---

## 2. 写入边界台账（全仓实证：核心 7 个 + 剩余历史跨界 2 个）

### 2.1 账号与权益核心写入方（7 个 · 合法归属）

| 文件（相对 `apps/api/app/`） | 当前写入范围 |
| --- | --- |
| `services/account_commands.py` | 受控账号命令入口（`set_user_avatar_url`、`set_user_role`、`set_user_status`、`set_user_trust_level`、`build_provisioned_user`，已收口 8 个跨界服务的直写） |
| `services/auth.py` | `User`、`UserSession`、`EmailVerificationCode`、`UserSecurityToken`、`UserRecoveryCode`、`user.email`、`user.status` |
| `services/chat_sso.py` | `UserSecurityToken`（OIDC 桥接审批码与会话状态） |
| `services/unified_auth.py` | `UserSecurityToken`（统一登录票据） |
| `services/product_access.py` | `ProductAccessGrant`（产品准入与权益） |
| `services/users.py` | `user.display_name`、`user.bio`（用户资料） |
| `services/privacy.py` | `User` 匿名脱敏、`UserSession` 撤销（匿名注销事务） |

### 2.2 剩余登记在账的受控历史跨界写入（2 个 · 已由 10 个收口至 2 个，禁止继续扩面）

| 分类 | 文件（相对 `apps/api/app/`） | 当前登记写入点 | 收口方向 |
| --- | --- | --- | --- |
| **社区成长** | `services/growth.py` | `UserPointEvent(` | 属社区成长事件表，非 `users` 主表写入；后续归社区域 |
| **系统建号（并行改动待合并）** | `services/daily_reading.py` | `User(` | 当前存在其他并行暂存改动，待其合入后再改用 `build_provisioned_user` |

> 其余全部业务模块（游戏目录、圈子帖子/评论、搜索、活动、推送、流量统计等）**严禁新增对上述 7 张表的直接写入**，由 `.github/scripts/verify_account_write_boundaries.mjs` 静态守卫强制拦截。

---

## 3. 跨表外键台账（全仓实证：75 条 `ForeignKey("users.id")` 分布于 20 个模型文件）

| 模型文件 | `users.id` 外键数 | 说明 |
| --- | --- | --- |
| `models/forum.py` | 11 | 板块、帖子、回复、编辑历史等社区核心内容 |
| `models/moderation.py` | 11 | 举报、审核记录、处罚历史 |
| `models/integration.py` | 7 | API Key、Webhook 与集成归属 |
| `models/user.py` | 6 | 账号域内部子表（会话、验证码、安全票据、恢复码、积分事件） |
| `models/badge.py` | 5 | 徽章授予与审核 |
| `models/daily_report.py` | 5 | 每日手账/报告会话与资料 |
| `models/interaction.py` | 5 | 点赞、收藏、通知等互动 |
| `models/email.py` | 3 | 邮件投递与偏好 |
| `models/product_access.py` | 3 | 产品准入授予、操作人与撤销人 |
| `models/social.py` | 3 | 关注、私信与拉黑 |
| `models/space.py` | 3 | 个人空间记录 |
| `models/event.py` | 2 | 活动创建与报名 |
| `models/search.py` | 2 | 搜索日志与索引归属 |
| `models/admin.py`、`models/ai.py`、`models/analytics.py`、`models/backup.py`、`models/catalog.py`、`models/draft.py`、`models/news.py`、`models/push.py`、`models/upload.py` | 各 1（共 9） | 审计、AI 记录、分析、备份、游戏目录投稿、草稿、新闻、推送、上传 |

**架构结论**：75 条物理外键分布在 20 个业务模型中，证明阶段 1 与阶段 2 必须**保留同 MySQL 实例与现有外键**；只有在阶段 3 具备充分证据时，才按业务域逐表解外键。

---

## 4. 耦合本地事务台账（6 类 · 拆独立账号进程前必须先有等价路径）

| 事务场景 | 代码入口 | 同事务耦合写入 | 未来拆进程前的前置改造 |
| --- | --- | --- | --- |
| **1. 用户注册** | `services/auth.py::register` | `User` + `EmailVerificationCode` + `IntegrationService.enqueue_event` | Webhook/验证邮件改为账号事务后幂等投递或独立 outbox |
| **2. 登录 / 2FA 登录** | `services/auth.py::login`、`verify_two_factor_login` | `UserSession` + `_award_daily_login`（社区 `UserPointEvent`） | 每日登录奖励改为登录后异步/弱耦合事件，不阻断登录 |
| **3. 邮箱验证** | `services/auth.py::verify_email` | `User` + `GrowthService.award` + `IntegrationService.enqueue_event` | 成长奖励与 Webhook 从验证事务解耦 |
| **4. 密码重设 / 邮箱变更** | `services/auth.py::request_password_reset`、`request_email_change` | `UserSecurityToken` / `EmailVerificationCode` + `BackgroundJobService.enqueue_email` | 明确邮件投递最小载荷契约与防重发语义 |
| **5. 匿名注销** | `services/privacy.py::_anonymize` | `User` 脱敏 + `UserSession` 撤销 + `DailyReport`/`ApiKey`/`Webhook`/`Notification`/`Board`/`SearchDocument`/邮件日志与队列脱敏 + 审计日志 | 拆分为“账号域立即停用与撤销会话” + “各业务域幂等清理编排与对账” |
| **6. FableSpace 票据与准入** | `services/auth.py::issue_fablespace_sso_ticket`、`exchange_fablespace_sso_ticket`、`introspect_fablespace_access` | `UserSecurityToken` 单次消费 + `User` 活跃状态 + `ProductAccessGrant` 实时复核 | 完整保留单次消费与基础准入退回语义，切流前须由 FableSpace 负责人联调验收 |

---

## 5. 静态守卫运行方式

```powershell
node .github/scripts/verify_account_write_boundaries.mjs
node --test .github/scripts/verify_account_write_boundaries.test.mjs
```
