# 平行线统一登录

`/chat/` 使用主站 `/auth` 的登录和注册入口。有效主站账号经过标准 OIDC Authorization Code、PKCE、state/nonce 校验后，以固定 issuer + 主站稳定用户 ID 建立聊天身份。旧聊天账号和历史数据保留，不按邮箱自动合并，也不复制主站密码或把主站 JWT 放进 URL。

认证服务只接受 `parallellines-chat` 和固定回调 `https://pingxingxian.space/chat/oauth/openid/callback`。主站一次性批准码由服务端兑换；聊天 API、刷新和私有图片继续核验原主站会话与账号状态。聊天退出先由服务端撤销当前聊天绑定，再执行原生会话清理并返回主站 `/auth`，旧 ID token 也不能重放。它不注销其他主站标签页。主站退出、停用或原登录过期后，所有对应聊天绑定拒绝访问；认证服务不可用时拒绝访问。

登录资格和 GPT 资格分开。新聊天身份是普通 USER，默认模型列表为空；此发布继续叠加 `compose.disabled.yaml`，真实 OpenAI Key 在进程环境中强制为空。不创建管理员，不自动赋予模型或额度权限。原生管理员 OAuth 兑换和旧密码登录已拒绝；后台身份迁移需另行处理。

## 服务端文件

- 原有 `deploy/librechat/.env`、五项应用密钥和模型候选保持原字节。
- `deploy/chat-sso/.env`：`CHAT_OIDC_CLIENT_SECRET`、`CHAT_OIDC_COOKIE_KEYS`、`CHAT_SSO_BRIDGE_SECRET`、`OPENID_SESSION_SECRET`，权限 `0600`。
- `deploy/chat-sso/secrets/signing.jwks.json`：RSA 3072 / RS256 私签名 JWK，权限 `0600`，容器 UID 1000 可读；私钥不会进入环境变量或响应。
- `deploy/chat-sso/data/oidc.sqlite`：单进程 OIDC 会话、刷新和授权记录，目录 `0700`。
- 主站 `apps/api/.env`：只增加/更新 `CHAT_SSO_ENABLED=true`、`CHAT_SSO_LOGIN_POLICY=active_main`、固定 `CHAT_SSO_FINISH_URL` 和同一 `CHAT_SSO_BRIDGE_SECRET`。

`initialize-sso.cjs /opt/parallellines` 生成缺失的上述五组材料。已有不同非空材料会拒绝覆盖；脚本不打印任何值。不要删除或随意更换材料；更换会使既有聊天登录失效。

## 发布与维护

先让正常 scoped Deploy 完成主 API、Web 和 Nginx 更新，再运行 Actions **Deploy family chat / mode=sso**。它使用原有 SSH 通道，启动 `chat-oidc`，只重新加载主 API 环境并重建聊天容器；不创建账号，不调用模型，不改变游戏目录数据。新增 sidecar 没有主机端口，使用既有 `parallellines_default` 网络。

服务器手动重启（`REVISION` 填实际部署 commit）：

```sh
cd /opt/parallellines/deploy/librechat
export CHAT_SSO_RELEASE=REVISION
sudo --preserve-env=CHAT_SSO_RELEASE docker compose \
  --env-file .env --env-file ../chat-sso/.env \
  -f compose.production.yaml -f compose.disabled.yaml -f compose.sso.yaml \
  up -d --wait chat-oidc librechat
```

不要去掉 `compose.sso.yaml` 来重启，否则会恢复旧认证配置。真实 GPT 启用仍由用户自行填写 Key，再另行给予适用账号模型权限；不需要把 Key 发到聊天。

## 版本与验证边界

LibreChat 固定 `v0.8.9-rc1` / `8d3da9bbb220a0a96be9330a2e1cbd385fb786d5`，镜像 digest 和本次挂载适配见 Compose 与 `sso/runtime/SOURCE.json`。认证服务依赖和 Node 基础镜像均锁定。适配使用原生鉴权、所有者/ACL 校验，再补主站实时状态；不得关闭鉴权或扩大文件访问范围。

本地已有真实 FastAPI 隔离数据库检查与 OIDC/会话模块测试。用户选择直接生产受控验证，不启动本机 Docker，也不把完整 CI 容器联测当发布前置。生产检查应分别记录匿名跳转、正常用户回调/刷新、主站退出后的拒绝、图片权限的实际结果；未执行项不得标成通过。

只支持单个 LibreChat 与单个 OIDC 进程。尚未验证真实付费模型的流式取消和费用行为。新实例中的旧密码账号仍保留数据但不能直接登录；不自动将主站管理员映射为聊天管理员。
