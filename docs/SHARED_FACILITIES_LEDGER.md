# 主站内部共享设施归属与运行边界台账（阶段 1 · 同进程收口）

核对日期：2026-11-23。依据 `SHARED_SERVICES_EXTRACTION_PLAN.md` 第 3、5 节要求，基于 `ParallelLines/apps/api/app/` 当前源码核查整理。本文明确主站内部 5 类共享设施的**生产者、消费方、唯一调度方、载荷权限与演进边界**；不新增公共服务或通用消息平台。

---

## 1. 通用后台队列（`BackgroundJobService`）

| 维度 | 本地源码实证 |
| --- | --- |
| **模型与核心服务** | `models/background_job.py`（`BackgroundJob`）、`services/background_jobs.py`（`enqueue_email`、`enqueue_notification`、`enqueue_due_scheduled_jobs`） |
| **生产者（11 个）** | `services/auth.py`（认证邮件入队）、`services/admin.py`、`services/backups.py`、`services/community_schedule.py`、`services/email_notifications.py`、`services/forum.py`、`services/integrations.py`、`services/interactions.py`、`services/moderation.py`、`services/social.py`、`services/background_jobs.py` |
| **消费与调度进程** | `workers/background_jobs.py`（主站通用 worker）、`workers/community_content.py`（社区内容调度 worker） |
| **隔离与演进边界** | 认证邮件载荷与普通社区/维护任务同库入队；**现有通用抢占不能据此认定多实例并发安全**，必须先按用途隔离载荷权限与防重语义、演练在途任务接管后，才可评估双跑或独立 worker。 |

---

## 2. 邮件投递（`email.py` / `email_notifications.py`）

| 维度 | 本地源码实证 |
| --- | --- |
| **投递与偏好模块** | 底层投递：`services/email.py`（`send_email`）；通知与订阅偏好：`api/v1/email.py`、`services/email_notifications.py` |
| **核心调用方** | 账号认证邮件：`services/auth.py`（通过 `enqueue_email` 同事务入队）；业务通知：`services/email_notifications.py`、`workers/background_jobs.py` |
| **隔离与演进边界** | 只共享底层投递适配与回执；**验证码与重置凭据生命周期归账号域，通知偏好归产品域**。严禁开放“供任意产品读取认证邮件载荷或提交任意收件人与正文”的通用接口；匿名注销须继续联动 `privacy.py::_redact_background_email_payloads` 脱敏在途载荷。 |

---

## 3. 媒体与上传适配（`UploadService`）

| 维度 | 本地源码实证 |
| --- | --- |
| **核心模块** | `models/upload.py`（`Upload`）、`api/v1/uploads.py`、`services/uploads.py` |
| **调用方（4 个）** | `services/catalog_submissions.py`（游戏投稿封面）、`services/forum.py`（圈子内容附件）、`services/privacy.py`（注销清理）、`workers/background_jobs.py`（后台清理） |
| **隔离与演进边界** | 仅共享对象存储/CDN 交付适配，**文件记录、待审/公开权限与归属仍归主站**；Chat 附件与 Matrix 媒体权限各自归属原产品，不建全站统一文件库。头像直写已收口至 `services/account_commands.py::set_user_avatar_url`。 |

---

## 4. 跨站流量统计（`TrafficService` / `TrafficQueue`）

| 维度 | 本地源码实证 |
| --- | --- |
| **独立链路** | 入口：`api/v1/traffic.py`；队列：`services/traffic_queue.py`（独立 Redis 队列）；聚合与报表：`services/traffic.py`；消费：`workers/traffic.py` |
| **隔离与演进边界** | 沿用现有独立 Redis 队列与可选 worker，**不再另建采集平台**；默认关闭，采集满载或 worker 异常不得阻断主站或子产品核心链路。Tavern 与 FableSpace 未视作已接入。 |

---

## 5. Webhook 外发（`IntegrationService`）

| 维度 | 本地源码实证 |
| --- | --- |
| **核心模块** | `api/v1/integrations.py`、`services/integrations.py`（`enqueue_event`） |
| **事件生产者（3 个）** | `services/auth.py`（注册/邮箱验证事件）、`services/forum.py`（社区事件）、`services/moderation.py`（审核事件）；由 `workers/background_jobs.py` 异步投递 |
| **隔离与演进边界** | 可复用外发签名与重试适配，不集中各产品 API Key、入站回调或历史导入逻辑；匿名注销继续联动 `privacy.py::_disable_webhooks` 与 `_disable_api_keys`。 |

---

## 6. 阶段 1 收口结论

至此，`SHARED_SERVICES_EXTRACTION_PLAN.md` 阶段 1 要求的全部本地台账与防越界护栏均已齐备：
1. **账号域**：[ACCOUNT_WRITE_BOUNDARY_LEDGER.md](ACCOUNT_WRITE_BOUNDARY_LEDGER.md) + `account_commands.py` + `verify_account_write_boundaries.mjs`（184 文件实扫，历史跨界直写 10 → 2）；
2. **跨站运维与共享网关**：`.github/ops-domains.json` + `verify_ops_boundaries.mjs` + `select_compose_files.sh` + `verify-gateway-sites.mjs`；
3. **主站内部共享设施**：本文（后台队列、邮件投递、媒体上传、跨站流量统计、Webhook 外发 5 类设施的唯一归属与演进红线）。
