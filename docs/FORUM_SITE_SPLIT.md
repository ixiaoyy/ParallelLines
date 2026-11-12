# 圈子独立站（原论坛）：本地实现与发布配方

状态：2026-11-12 发布候选。用户已授权本次圈子拆分与导航调整提交、推送和生产部署；生产启用与验收待执行，结果以本次发布回执为准。

## 1. 产品与数据边界

| 入口 | 职责 |
| --- | --- |
| `https://pingxingxian.space/` | 游戏目录；原 `/games` 入口继续可用 |
| `https://forum.pingxingxian.space/` | 对外名称为圈子，保留原主站的完整论坛：版块、帖子、回复、成员、私信、通知与论坛后台 |
| `https://tools.pingxingxian.space/` | 现有独立工具站 |
| `https://chat.pingxingxian.space/` | 现有聊天站；导航直接进入，不传令牌或更改 Chat 登录协议 |

产品导航统一为 `游戏｜圈子｜工具｜聊天`。仅调整对外名称，`forum.pingxingxian.space`、`forum` 技术标识、原功能及数据不变。

论坛与游戏站在同一个仓库维护，共用成熟的前端源码、依赖锁和现有 API；论坛有自己的 Vite 模式、`dist-forum`、容器镜像、域名与发布版本。没有复制另一套源码或新增数据库、身份服务。本批不迁移帖子、账号、上传文件，不增加数据库迁移。

主站仍保留旧论坛 SPA 兼容路由，避免破坏共享账号和 Chat 登录；独立不代表从主站构建中彻底删除全部旧兼容代码。启用论坛覆盖后，公网旧书签和刷新由 Nginx 迁移，正常四产品导航直接到各自站点。

账号继续来自同一 API。浏览器令牌位于各来源的 `localStorage`，论坛需要用原账号重新登录；本批没有跨子域自动登录。主域 `/auth`、`/account*`、Chat SSO/OIDC 和目录后台 `/admin` 不迁移。论坛域内 `/admin` 由前端归一化为 `/admin/forum`。

## 2. 接线与默认行为

- `apps/web/Dockerfile.forum`：按现有 pnpm 锁构建 `build:forum`，发布 `dist-forum`；不持有账号、证书或数据。
- `docker-compose.forum.yml`：显式覆盖文件，新增 `forum-web`，向原 API 设置 `PUBLIC_FORUM_URL` 与 `FORUM_WEB_APP_SHELL_URL`，给原 Nginx 增加两份只读挂载。
- `deploy/nginx/forum.conf`：论坛域入口。同源 `/api/`、`/uploads/` 仍访问原 API；公开论坛页、站点地图及旧短链沿用原语义 HTML；其他页面使用论坛静态前端。仅 API 5xx 回退对应论坛外壳。
- `deploy/nginx/forum-main-redirects.conf`：主域旧论坛入口转向论坛，保留查询串；浏览器按标准继承未被新地址替换的片段。首期 Nginx 使用 `302`，避免恢复时遗留永久跳转缓存。
- `deploy/nginx/default.conf`：只新增可选 glob include；没有论坛覆盖挂载时仍走原站配置，也不要求论坛证书。
- `.github/scripts/select_compose_files.sh`：所有四条远程发布路径选择 Compose 文件时读取服务端启用标记；默认不启用论坛。

新增 API 配置仅用于独立论坛：

```text
PUBLIC_SITE_URL=https://pingxingxian.space
WEB_APP_SHELL_URL=http://web/index.html
PUBLIC_FORUM_URL=https://forum.pingxingxian.space
FORUM_WEB_APP_SHELL_URL=http://forum-web/index.html
```

前两项保持原含义，不能全局改成论坛地址。后两项由论坛 Compose 覆盖注入，不编辑真实 `.env`。没有后两项时 API 保留旧行为。论坛站点地图与规范地址单独处理，不将游戏目录改到论坛域。

## 3. 本地使用与证据

从仓库根目录执行：

```powershell
pnpm build:forum
pnpm --dir apps/web exec vite preview --outDir dist-forum --port 5175
```

论坛预览使用配置好的 API，真实登录、发帖会有副作用；仅看页面时使用定向浏览器测试的 API 替身，不把预览地址接到未知数据库。类型检查沿用 `pnpm typecheck:web`。

本地已完成的证据：

对外名称随后按用户要求改为 `圈子`。本轮只重测命名相关范围：API 6 项、主站/圈子 5 项定向检查（含静态元信息与生产产物页面）、工具页脚及手机菜单 2 项通过；原域名、链接、数据和业务流程的未变证据沿用。工具英文名复用 `Community`，同时实测修正长名称在窄屏与返回顶部按钮的间距。

- 前端类型检查、定向 ESLint、游戏站与论坛站构建通过；保留 Vite 大 chunk 告警，没有调高阈值掩盖。
- 主站 19 个定向浏览器用例、论坛 3 个定向浏览器用例通过，API 与站外目标均为替身。覆盖四产品导航、论坛根页与旧首页参数/片段、主题详情、原账号登录回跳、发帖回复和权限。
- 320、390、921、1440 宽度的实际页面截图已检查，无横向溢出。四入口至少 44×44；320 极窄屏的游戏顶栏另起产品导航行，已检查登录前后品牌、通知和账号均不被遮挡。两套生产产物入口也已做浏览器复核；不替代真人手机验收。
- API 90 项无数据库、无网络的定向测试通过；新论坛根标题对齐后另重测相关 3 项通过，其他未变证据沿用。覆盖域名选择、公开/私有/不存在状态、独立外壳、规范地址与 sitemap/robots 隔离；没有把替身数据当作真实业务数据验收。
- 独立工具仓库的页脚与中英文译文也同步四产品入口。真实工具页的定向浏览器回归覆盖 320、390、1280 宽度、同标签切换、至少 44×44 的链接目标及窄屏返回顶部避让；手机菜单旧行为和定向 ESLint 通过。其余既有工作区改动保留。
- 基础 Compose、基础加论坛覆盖、基础加现有数据迁移覆盖再加论坛覆盖，均通过 Compose 客户端配置校验；新增挂载没有移除原有证书目录、数据路径或网络。
- `.github/scripts/test_forum_deploy.py` 的 9 个离线测试通过：默认不启用、锁定论坛镜像、拒绝无效标记、缺配方/证书/镜像停止、脚本语法，以及四条工作流路径接线。sudo、证书及镜像是替身，不接触服务器或 Docker daemon。

未完成的环境验收：Docker daemon 当前不可用，因此没有执行论坛镜像构建、真实 `nginx -t`、容器健康或 TLS 检查；也没有查询真实论坛数据、执行真实登录/发帖、运行 GitHub Actions 或验证线上页面。工具仓库的 React Doctor 没有已安装命令，本次未安装或执行，定向浏览器与 ESLint 证据不能代替该诊断。上述事项由后续具备对应环境和授权的执行者完成；运行环境未验收时不得启用论坛标记或报告上线完成。

## 4. 服务端启用标记

服务端工作目录使用 `.deployment/forum-enabled`，内容为**一行已构建并加载的论坛镜像标签**，例如 `forum-20261112-1`。它是非敏感运行状态，不进入 Git，不作为 shell 脚本执行。标签只接受 Docker tag 字符且最多 128 字符。

标记存在时，原四条自动部署路径在原有基础及数据迁移覆盖后追加论坛覆盖，并使用该标签的 `parallellines-forum-web` 镜像。配方、论坛证书或已加载镜像任一缺失都会停止；不会静默退回基础 Compose，也不会因一次主站更新重建并覆盖论坛标签。全量和 bootstrap 会恢复已发布的论坛容器，论坛版本仍由独立发布决定。

标记不存在时不新增论坛服务或证书前置条件。不要通过删除标记绕过缺失前置条件；只有获准关闭论坛并执行下文恢复流程时才移除标记。回退到没有本脚本/论坛配方的旧源码也不兼容已启用状态，不能直接按旧工作流覆盖。

## 5. 后续获准发布时的顺序

以下是配方，不表示已获得上传、构建服务器、证书申请、服务重建或数据迁移权限。执行者须先确认本次目标环境、当前 Compose 文件链、数据卷、发布版本与恢复版本。若真实环境使用现有 `deploy/docker-compose.migration.yml`，必须保留它；不能用根 Compose 替换真实部署。

1. 保存当前源码版本、镜像标签、Nginx 配置及实际 Compose 文件链，保留论坛上个版本镜像。确认主站/API/Chat/工具的独立健康入口及可用恢复通道，核对所有相关更改和依赖已经包含在交付版本。
2. 先完成独立论坛镜像构建与加载；以已审核的源码版本构建不可变标签，不能只把未提交工作区的 `HEAD` 当成完整源码身份。命令示意：

   ```sh
   docker build -f apps/web/Dockerfile.forum \
     --build-arg SOURCE_REVISION="$SOURCE_REVISION" \
     -t "parallellines-forum-web:$FORUM_IMAGE_TAG" .
   ```

3. 确认论坛 DNS 指向目标入口，HTTP ACME challenge 路径实际可用。当前基础 Nginx 的 HTTP 默认入口已提供该 challenge 路径；先通过它准备 `forum.pingxingxian.space` 证书，不先挂载依赖证书的论坛 HTTPS vhost。证书在宿主机的目标路径：

   ```text
   /opt/parallellines/var/letsencrypt/live/forum.pingxingxian.space/fullchain.pem
   /opt/parallellines/var/letsencrypt/live/forum.pingxingxian.space/privkey.pem
   ```

4. 用实际基础文件链加 `docker-compose.forum.yml` 做配置校验，不把展开后的密钥环境打印到日志。先完成真实 Nginx 配置检查、独立镜像与 API 版本核验。API 原启动命令仍执行 `alembic upgrade head`；本需求无新迁移不代表服务器上没有其他待执行迁移，必须先核对并取得相应授权。
5. 暂停与本次手动激活竞争的发布，在 `.deployment/forum-enabled` 写入已加载的镜像标签，记录原标记内容（如有）。source 发布选择脚本后，用它给出的文件链协调更新 API、启动论坛静态服务、启用 Nginx vhost 与旧链接迁移；不要在论坛未可用时单独提前发布主站新导航。这些服务重建可能短暂中断请求，不承诺零停机。
6. Nginx 检查失败时不 reload；新论坛入口、旧链接和主站回归通过后，再恢复正常发布。后续独立论坛前端升级只构建/加载新的论坛标签、更新标记并使用完整文件链重建 `forum-web`，不随之替换共享 API 或数据服务。

启用后至少检查：

- 主域 `/`、`/games` 仍为游戏；已有游戏、工具、Chat/OIDC 和目录后台不变。
- 论坛 `/` 为完整论坛，`/forum?title=...#...` 归一化到根并保留筛选和定位。
- 主域旧 `/forum`、版块、帖子、成员、短链与论坛后台进入论坛；原查询与片段保留。未知/私有主题仍维持真实不存在和权限语义。
- 登录注册、登录回跳、发帖回复、私信、通知、上传和论坛后台使用同一套既有账号数据；论坛登录不意外提升权限，Chat 入口没有携带论坛令牌。
- 两站 canonical、robots、sitemap、首屏 HTML 与实际加载的独立前端版本一致；手机布局、键盘焦点、页脚四入口均可用。
- 观察一次后续 API/Nginx/主站发布后，论坛标记版本、环境变量和挂载仍被保留；这项需要真实 Actions/服务端验收，离线脚本测试不能代签。

## 6. 恢复

仅在本次恢复动作获准后执行，先停住竞争发布。首选把标记改回已记录的上一论坛镜像标签，用相同完整 Compose 文件链重建 `forum-web`，保留共享 API 与数据。恢复后重新核论坛入口、旧链接、登录和主站/Chat 健康。

如需撤销整个论坛独立入口，先恢复主站导航及兼容前端版本，再移除启用标记，以原实际基础文件链重建 API 和 Nginx，使其撤掉论坛环境和可选挂载。不得使用 `down -v`、清空数据库、覆盖上传目录或回退共享账号数据。论坛静态容器和旧镜像可以先保留作恢复依据；不擅自清理它们。

API 曾对旧 `/forum` 给出的 `301` 可能已被浏览器缓存，因此整站撤销时仍应暂留论坛域的兼容入口或有范围的恢复跳转，不能仅靠移除 Nginx 的 `302` 就宣称所有客户端已恢复。证书续期目录、原 Chat/New API 内部凭据和它们各自的回退保护也不能随论坛恢复删除或降级。
