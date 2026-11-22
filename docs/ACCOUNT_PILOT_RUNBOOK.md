# 阶段 2 独立账号服务试点运行与回切手册

依据 `SHARED_SERVICES_EXTRACTION_PLAN.md` 第 5 节（阶段 2），本试点仅在**完成既有能力验收并获得明确授权**后按需启用；本地就绪不代表线上已切流。

## 1. 试点边界（不可违背）

- **唯一启动入口**：`apps/api/app/account_main.py`（通过 `docker-compose.account-pilot.yml` 以 `127.0.0.1:8001` 回环启动）。
- **唯一迁移责任方**：`account-api` **不执行** `alembic upgrade head`，数据库迁移仍只由主站 `api` 唯一负责。
- **路由范围**：仅承接 `/api/v1/auth/*`（含 `chat-sso`、`unified`、`fablespace` 票据）、`/api/v1/users/*`、`/api/v1/invites/*` 及 `/healthz`、`/readyz`。
- **同库兼容**：初期与主站共用现有 MySQL / Redis，不改表结构、不拆外键、不更换 OIDC Issuer URL（`https://pingxingxian.space/auth/oidc`）或 `sub`。

## 2. 切流前门槛

1. 先通过一键本地静态守卫：`node .github/scripts/run_architecture_guards.mjs`。
2. 启动试点容器并确认 `GET http://127.0.0.1:8001/readyz` 返回 `200 {"status":"ready","service":"parallellines-account-api"}`。
3. 明确切流观察窗口、错误率/延迟/撤销时效阈值及回切责任人。

## 3. 试点与回切

- **试点切流**：仅在共享 Nginx 网关的单一发布链中，将 `/api/v1/auth/`（可先从只读/登录路径小范围试点）指向 `account-api:8001`，经 `nginx -t` 校验后平滑 `reload`。
- **零数据损失回切**：若观察期内出现异常，只需将 Nginx 上游切回原 `api:8000` 并 `nginx -t && nginx -s reload`，再停止 `account-api` 容器；因同库兼容且无分库双写，旧会话与切流期间产生的新会话均保持有效。
