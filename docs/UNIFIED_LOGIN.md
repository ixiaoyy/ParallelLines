# 主站统一登录：本地候选与发布边界

## 范围和行为

主站是唯一普通账号凭据入口；圈子、Chat、New API 使用主站稳定用户 ID 和当前浏览器会话。
公开内容均可匿名进入，受限操作再引导登录。Chat 游客可以输入草稿，发送、选模型、历史和上传需要登录；
返回后恢复草稿但不自动发送。界面不展示验收、协议或草稿存储机制说明，仅在实际失败时提供必要恢复操作。

- 圈子复用原 API、账号、帖子和权限，不另建账号库。
- 工具现有公开页面没有账号能力，不新增登录门槛。
- FableSpace 明确不纳入本次统一登录，既有 ticket/exchange/introspect 与外部部署保持不变。
- 管理员紧急恢复入口属于独立运维边界，不向普通用户开放，不用统一登录状态自动升权。
- 退出/换号只撤销当前浏览器所绑定的主站会话和其下游绑定，不全账号踢出其他设备。
- 主站不可用与未登录是不同状态：公开页继续可见，不能伪造已退出或使用旧身份进入受保护页面。

## 主站与圈子接线

API：`apps/api/app/api/v1/auth_unified.py`、`services/unified_auth.py`、`schemas/unified_auth.py`。
前端：`apps/web/src/features/auth/unified/` 与 `pages/auth/Unified*.vue`。

| 边界 | 实现 |
| --- | --- |
| 中央凭据 | 主站 host-only `__Host-pl-unified`，Secure/HttpOnly/SameSite=Lax/Path=/；不设 Domain |
| 旧主站迁移 | 无中央 Cookie 时可迁移原带 sid 的主站会话；已有中央 Cookie 不接受旧本地身份覆盖 |
| 显式换号 | 真正完成主站登录后才 `bootstrap(replace=true)`；浏览器指针代次与父 sid 序列化，旧响应不可认领新身份 |
| 圈子登录 | 固定 client `parallellines-circle`，S256 PKCE、一次码60秒、固定 `/auth/unified/callback`；不传 refresh |
| 圈子 API | 最长300秒原生 access；401仅同身份续发，换号中不把旧操作重放给新账号 |
| 状态通知 | 主站 `/auth/unified/state`，固定来源/source/request_id；只传 authenticated/subject/auth_epoch/available |
| 退出 | 一次票据到主站 `/auth/unified/logout`，旧票据不清后来换成的新账号 |
| 私有缓存 | 切换先隔离请求上下文、取消旧查询并清缓存，迟到响应和迟到清缓存不能覆盖新账号 |

没有新增数据库表/列或迁移；浏览器指针、授权码和退出票据复用既有安全令牌表。
主站 access/refresh 不写入跨域 URL、状态消息、Chat/New API Cookie；各站保留自己的受约束原生会话。

## 下游候选

本次交付只保留部署需要的运行产物和增量材料；修改继续在 GitHub 维护。不额外重打上游完整源码归档，也不新增产品页脚或源码下载提示。

- Chat：同级 `parallellines-chat/openwebui-profile-overlay/unified-login/README.md` 和 `identity-bridge/rp-session.mjs`。
  RP（依赖方）使用各自既有客户端凭据调用发行方，不分发主站桥密钥；只有可信 `pl_unified_browser=true` 绑定可进入新浏览器会话。
- New API：同级 `parallellines-new-api/releases/v0.13.2-pkce.10/` 的独立候选配方。
  必须使用完整顺序补丁及清单，不用根 pkce.3 构建代替；模型代理、计费、额度与原生角色合同不变。
- 公网代理拒绝 Chat `/api/v1/auths/unified/recovery` 和 New API `/root-recovery`、`/api/user/root-recovery` 及子路径。
  本地恢复端口与关闭代理头等要求见对应候选说明，不能仅凭 Host 白名单认定请求来自回环。

## 开关和发布前置

候选的开关默认关闭，正式启用使用定向发布配置，不直接改真实 `.env`。
本次用户已授权提交、推送并在服务器运行验收。已完成生产只读盘点，尚未切换应用；实际上线结论以本轮发布回执为准。

1. 后端使用 `UNIFIED_AUTH_ENABLED`；生产不得开启 `UNIFIED_AUTH_ALLOW_LOOPBACK_HTTP`。
2. 主站和圈子均以 `VITE_UNIFIED_AUTH_ENABLED=true` 重新构建；Docker 与 Compose 提供显式 build arg，默认false。
   CI 和手动主站构建读取同名仓库变量。圈子仍按独立站发布流程，不复用旧 community 固定版本发布脚本。
   启用后由 `.deployment/unified-auth-enabled` 和 `docker-compose.unified.yml` 接续后续发布；该覆盖只保存功能开关，不固定主站镜像或保存凭据。
3. 正式来源固定为主域、forum、chat、api；Web示例里的 `VITE_UNIFIED_*_ORIGIN` 仅供显式回环多源测试。
4. 按 Chat 与 New API 候选说明配置其开关、发行方和唯一客户端凭据；先部署支持新协议的后端/发行方，再启用下游与前端。
5. 安装完整代理私密路由头和恢复入口公网拒绝规则；不增加全站登录墙。实际 `nginx -t` 与浏览器 frame/Cookie 检查属于发布验收。
6. 运行一次真实主站登录→圈子→Chat→New API、匿名受限操作、同浏览器退出/换号及另设备不被退出的端到端检查。
   Chat 模型实际调用/计费仍需要独立授权，不因登录检查顺带消费模型额度。

## 当前验证与未完成验收

- Main API：46项统一登录隔离测试及18项原 Chat/资料回归通过，使用独立 SQLite/ASGI，无真实业务库。
- Main/Circle Web：27项协议/缓存/401与旧refresh兼容单测通过；真实浏览器跨源 iframe/PKCE页面在受控 API 下通过匿名、无密码接续、换号丢弃旧响应、故障不伪退出、退出清缓存。
  错误页已检查390px实际截图。API均拦截，无模型、帖子、文件、真实用户写入。
- Chat：完整前端候选构建和1440/390/320游客页渲染、发送/选模型/历史/上传登录引导已验；草稿保留且不自动发送。
- 2026-11-15 用户批准隔离测试依赖后，发行方在独立候选目录按原 lock 安装42个包（忽略安装脚本、不改版本），真实 OIDC/provider/multiclient/sqlite-adapter 测试37通过、1项Windows权限专项跳过。Main上游仍为本地替身，不能代替四站真实入口验收。
- MySQL真实行锁并发、实际Cookie/代理/多站登录以及生产版本均未验收。负责人为本次集成/发布执行者；恢复条件为依赖就绪和目标环境授权。
- Nginx 已补 `deploy/nginx/default.conf`、`deploy/nginx/forum.conf`、`apps/web/nginx.conf` 的私密路径、精确 frame 和公网恢复拒绝规则；双层静态矩阵通过。本机没有 nginx 可执行文件且 Docker daemon 未运行，未运行 `nginx -t`，不得据此直接切换线上配置。
- 混合工作区的类型检查曾被另轮未暂存 Space 调用阻断，未修改或混入该轮源码。2026-11-15 从 Git index 独立导出本次 Main/Circle 候选后，实际 `vue-tsc -b` 和两套 Vite 生产构建均通过；后续交付继续使用独立候选，不以混合工作区生成发布产物。
- Docker运行时目录已按用户逐项批准备份；一次重启后仍在独立Secrets Engine端点失败，已停止修复，未清镜像/卷/虚拟磁盘。用户随后明确停止本地Docker及额外本地验收，改在服务器直接运行；服务端配置、健康和真实登录继续由本次发布负责人完成，不把未做的本地MySQL验证写成通过。

定向复现（使用已安装依赖，不触发真实业务写入）：

```powershell
pnpm --dir apps/web exec vitest run --config vitest.unified-auth.config.ts
$env:NO_PROXY='127.0.0.1,localhost'
# 使用本机已有Playwright Chromium；必要时显式指定PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH，不自动下载。
pnpm --dir apps/web exec playwright test --config playwright.unified.config.ts
```

浏览器检查共5项，包括在途A兑换遇B换号以及同页401后的真实匿名/网络故障区分。
测试配置仅启动4183/4184回环站点并拦截全部API及外网请求，不向真实主站、Chat或模型发送请求。

恢复应整组回到已记录的兼容前端、API/发行方与下游版本，保留数据库、账号及恢复入口。
关闭新开关只恢复旧协议能力，不会自动恢复已撤销的旧浏览器会话；用户需要按恢复版本正常登录。
